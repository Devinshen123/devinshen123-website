args <- commandArgs(trailingOnly = TRUE)
root <- if (length(args)) normalizePath(args[[1]], mustWork = TRUE) else getwd()
out <- file.path(root, "results", "comparison")
dir.create(out, recursive = TRUE, showWarnings = FALSE)
suppressPackageStartupMessages({
  library(dplyr)
  library(tidymodels)
  library(slider)
})

study <- jsonlite::fromJSON(file.path(root, "study_config.json"))
data_cutoff <- as.Date(study$study_data_through)
test_start <- as.Date(study$test_start)
raw <- read.csv(file.path(root, "data", "daily_prices.csv"))
raw$date <- as.Date(raw$date)
raw <- raw[raw$date <= data_cutoff, ]
stopifnot(nrow(raw) == 116928L, max(raw$date) == data_cutoff,
          identical(unique(raw$symbol), c(study$symbols, study$benchmark)),
          !anyNA(raw), !anyDuplicated(raw[c("symbol", "date")]),
          all(raw$high >= pmax(raw$open, raw$close, raw$low)),
          all(raw$low <= pmin(raw$open, raw$close, raw$high)))

spy <- raw |>
  filter(symbol == study$benchmark) |>
  arrange(date) |>
  transmute(date, spy_adjusted = adjusted, spy_ret = adjusted / dplyr::lag(adjusted) - 1,
            spy_mom_21 = dplyr::lag(adjusted, 1) / dplyr::lag(adjusted, 22) - 1)

# Preserve the original feature formulas, including the inverse orientation of
# the three existing momentum ratios. Relative momentum is the only new input.
panel <- raw |>
  filter(symbol != study$benchmark) |>
  left_join(select(spy, -spy_adjusted), by = "date", relationship = "many-to-one") |>
  arrange(date) |>
  group_by(symbol) |>
  mutate(return = adjusted / dplyr::lag(adjusted) - 1,
         mom_1m = dplyr::lag(adjusted, 21) / dplyr::lag(adjusted, 1) - 1,
         mom_3m = dplyr::lag(adjusted, 63) / dplyr::lag(adjusted, 1) - 1,
         mom_6m = dplyr::lag(adjusted, 126) / dplyr::lag(adjusted, 1) - 1,
         vol_1m = slide_dbl(dplyr::lag(return), sd, .before = 21, .complete = TRUE),
         ret_5d = dplyr::lag(adjusted, 5) / dplyr::lag(adjusted, 1) - 1,
         excess_ret = return - spy_ret,
         relative_momentum_21 = (dplyr::lag(adjusted, 1) / dplyr::lag(adjusted, 22) - 1) - spy_mom_21,
         entry_date = dplyr::lead(date, 1),
         exit_date = dplyr::lead(date, 20),
         target = dplyr::lead(adjusted, 20) / dplyr::lead(adjusted, 1) - 1) |>
  ungroup() |>
  select(-spy_mom_21) |>
  tidyr::drop_na()

features <- c("open", "high", "low", "close", "volume", "adjusted",
              "return", "spy_ret", "mom_1m", "mom_3m", "mom_6m",
              "vol_1m", "ret_5d", "excess_ret")
added <- "relative_momentum_21"
train <- filter(panel, date < test_start, exit_date < test_start)
purged <- filter(panel, date < test_start, exit_date >= test_start)
test <- filter(panel, date >= test_start)
stopifnot(nrow(train) == 33725L, nrow(purged) == 1900L, nrow(test) == 66215L,
          max(train$exit_date) < min(test$date), max(test$exit_date) == data_cutoff,
          all(table(test$date) == 95L),
          !anyDuplicated(panel[c("symbol", "date")]))

# The instructor's model settings and seed are recorded in the study config.
original_spec <- do.call(boost_tree, study$boost_tree) |>
  set_engine("xgboost") |>
  set_mode("regression")

predict_model <- function(cols) {
  stopifnot(all(cols %in% features | cols == added))
  tr <- select(train, target, all_of(cols))
  te <- select(test, all_of(cols))
  set.seed(study$seed)
  m <- workflow() |>
    add_recipe(recipe(target ~ ., data = tr)) |>
    add_model(original_spec) |>
    fit(data = tr)
  p <- predict(m, te)$.pred
  stopifnot(length(p) == nrow(test), all(is.finite(p)))
  p
}

preds <- select(test, symbol, date, entry_date, exit_date, target, relative_momentum_21)
preds$historical_mean <- mean(train$target)
preds$original_xgb <- predict_model(features)
preds$relative_momentum_xgb <- predict_model(c(features, added))

# Run a prespecified robustness check for nominal-price/volume levels, which
# Yahoo can retrospectively rescale. This does not select the primary model.
return_features <- setdiff(features, c("open", "high", "low", "close", "volume", "adjusted"))
sensitivity <- preds
sensitivity$original_xgb <- predict_model(return_features)
sensitivity$relative_momentum_xgb <- predict_model(c(return_features, added))

summarize_predictions <- function(p) {
  ids <- c("historical_mean", "original_xgb", "relative_momentum_xgb")
  reference_mse <- mean((p$historical_mean - p$target)^2)
  bind_rows(lapply(ids, function(id) {
    e <- p[[id]] - p$target
    tibble(model = id, n = length(e), rmse = sqrt(mean(e^2)), mae = mean(abs(e)),
           r2_vs_training_mean = 1 - mean(e^2) / reference_mse)
  }))
}

# One scheduled signal per month. If its next-day entry would precede the
# prior exit, use that month's first feasible signal. A same-close switch is
# allowed; all strategies hold cash with zero interest outside these windows.
candidates <- distinct(preds, date, entry_date, exit_date) |>
  arrange(date) |>
  mutate(month = format(date, "%Y-%m"))
prior_exit <- as.Date("1900-01-01")
calendar <- bind_rows(lapply(split(candidates, candidates$month), function(g) {
  possible <- filter(g, entry_date >= prior_exit)
  if (!nrow(possible)) stop("No feasible entry for ", g$month[[1]])
  chosen <- slice_head(possible, n = 1)
  prior_exit <<- chosen$exit_date[[1]]
  mutate(chosen, calendar_first_signal = g$date[[1]], delayed = date != calendar_first_signal)
}))
calendar$spy_return <- spy$spy_adjusted[match(calendar$exit_date, spy$date)] /
  spy$spy_adjusted[match(calendar$entry_date, spy$date)] - 1
stopifnot(nrow(calendar) == 34L, all(calendar$entry_date[-1] >= head(calendar$exit_date, -1)),
          !anyNA(calendar$spy_return), all(calendar$date < calendar$entry_date),
          all(calendar$entry_date < calendar$exit_date))

portfolios <- function(p) {
  at_signal <- semi_join(p, select(calendar, date), by = "date")
  by_date <- group_by(at_signal, date)
  picks <- function(id) {
    by_date |>
      arrange(desc(.data[[id]]), symbol, .by_group = TRUE) |>
      slice_head(n = 10L) |>
      mutate(score = .data[[id]], positive = pmax(score, 0),
             weight = if (sum(positive) > 0) positive / sum(positive) else rep(1/n(), n()),
             model = id) |>
      ungroup()
  }
  w <- bind_rows(picks("original_xgb"), picks("relative_momentum_xgb"),
                 by_date |> mutate(score = historical_mean, weight = 1/n(), model = "equal_weight_95") |>
                   ungroup()) |>
    select(model, symbol, date, entry_date, exit_date, score, weight, target)
  trading <- w |>
    group_by(model, date, entry_date, exit_date) |>
    summarise(n = n(), weight_sum = sum(weight), gross_return = sum(weight * target),
              min_weight = min(weight), .groups = "drop")
  stopifnot(all(abs(trading$weight_sum - 1) < 1e-12), all(trading$min_weight >= 0),
            all(trading$n[trading$model != "equal_weight_95"] == 10L),
            all(trading$n[trading$model == "equal_weight_95"] == 95L))
  trading <- bind_rows(trading, transmute(calendar, model = "spy", date, entry_date, exit_date,
                                         n = 1L, weight_sum = 1, gross_return = spy_return, min_weight = 1)) |>
    group_by(model) |>
    arrange(date, .by_group = TRUE) |>
    mutate(wealth = cumprod(1 + gross_return)) |>
    ungroup()
  stopifnot(all(table(trading$model) == nrow(calendar)))
  list(weights = w, periods = trading, summary = trading |>
         group_by(model) |>
         summarise(windows = n(), first_entry = min(entry_date), last_exit = max(exit_date),
                   ending_wealth = last(wealth), gross_cumulative_return = ending_wealth - 1,
                   positive_windows = sum(gross_return > 0), .groups = "drop"))
}

base_prediction <- summarize_predictions(preds)
base_portfolio <- portfolios(preds)
sensitivity_prediction <- summarize_predictions(sensitivity)
sensitivity_portfolio <- portfolios(sensitivity)
audit <- list(data_through = as.character(data_cutoff), stocks = 95L, training_rows = nrow(train),
              purged_rows = nrow(purged), latest_training_exit = as.character(max(train$exit_date)),
              test_rows = nrow(test), test_signal_days = n_distinct(test$date),
              first_test_signal = as.character(min(test$date)), last_test_signal = as.character(max(test$date)),
              portfolio_windows = nrow(calendar), portfolio_signals_delayed = sum(calendar$delayed),
              first_portfolio_entry = as.character(min(calendar$entry_date)),
              last_portfolio_exit = as.character(max(calendar$exit_date)),
              fixed_training_forecast = mean(train$target), features_original = features,
              feature_added = added, features_robustness = return_features,
              r = as.character(getRversion()), xgboost = as.character(packageVersion("xgboost")))

save_csv <- function(x, name) write.csv(x, file.path(out, paste0(name, ".csv")), row.names = FALSE)
save_csv(preds, "test_predictions")
save_csv(sensitivity, "sensitivity_test_predictions")
save_csv(select(purged, symbol, date, exit_date), "excluded_training_labels")
save_csv(calendar, "common_windows")
save_csv(base_prediction, "prediction_metrics")
save_csv(base_portfolio$summary, "portfolio_metrics")
save_csv(base_portfolio$periods, "portfolio_periods")
save_csv(base_portfolio$weights, "portfolio_weights")
save_csv(sensitivity_prediction, "sensitivity_prediction_metrics")
save_csv(sensitivity_portfolio$summary, "sensitivity_portfolio_metrics")
save_csv(sensitivity_portfolio$periods, "sensitivity_portfolio_periods")
save_csv(sensitivity_portfolio$weights, "sensitivity_portfolio_weights")
jsonlite::write_json(audit, file.path(out, "audit.json"), auto_unbox = TRUE, digits = NA, pretty = TRUE)
print(base_prediction)
print(base_portfolio$summary)
print(sensitivity_prediction)
print(sensitivity_portfolio$summary)
