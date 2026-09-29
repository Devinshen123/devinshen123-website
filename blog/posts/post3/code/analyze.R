# Codes checked against the downloaded IPUMS DDI.
# Run from project folder: Rscript code/analyze.R data/raw/cps_XXXXX.xml
library(ipumsr)
library(dplyr)
library(ggplot2)
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1 || !file.exists(args[1])) {
  stop("Provide the downloaded IPUMS XML codebook; keep its matching data file beside it.")
}
dir.create("results", showWarnings = FALSE)
ddi <- read_ipums_ddi(args[1])
micro <- read_ipums_micro(ddi)
required <- c("YEAR", "MONTH", "ASECFLAG", "AGE", "EDUC", "EMPSTAT", "WTFINL")
stopifnot(all(required %in% names(micro)))
# Retain the code labels for a human check of the extract before publication.
capture.output(lapply(micro[c("ASECFLAG", "EDUC", "EMPSTAT")],
                      function(x) attr(x, "labels")), file = "results/code-labels.txt")
stopifnot(!any(micro$ASECFLAG == 1, na.rm = TRUE))
micro <- micro |> mutate(across(all_of(required), as.numeric))
months <- micro |> distinct(YEAR, MONTH)
stopifnot(nrow(months) == 24, all(months$YEAR %in% c(2019, 2024)),
          all(table(months$YEAR) == 12), !anyDuplicated(months[c("YEAR", "MONTH")]),
          all(months$MONTH %in% 1:12))

# Numeric recodes are specific to modern CPS; confirm against the supplied DDI.
groups <- c("Less than high school", "High school diploma",
            "Some college / associate", "Bachelor's or higher")
working_age <- micro |> filter(AGE >= 25, AGE <= 64)
write.csv(working_age |> count(YEAR, EDUC, EMPSTAT, name = "records"),
          "results/observed_codes.csv", row.names = FALSE)
data <- working_age |>
  mutate(education = case_when(
    EDUC %in% c(2, 10, 20, 30, 40, 50, 60, 71) ~ groups[1],
    EDUC == 73 ~ groups[2],
    EDUC %in% c(81, 91, 92) ~ groups[3],
    EDUC %in% c(111, 123, 124, 125) ~ groups[4],
    TRUE ~ NA_character_),
    valid_status = EMPSTAT %in% c(10, 12, 20, 21, 22, 30, 31, 32, 33, 34, 35, 36),
    employed = EMPSTAT %in% c(10, 12),
    unemployed = EMPSTAT %in% c(20, 21, 22),
    labor_force = employed | unemployed) |>
  filter(valid_status, !is.na(education), is.finite(WTFINL), WTFINL > 0)
write.csv(data.frame(age_eligible_records = nrow(working_age),
                     retained_records = nrow(data),
                     excluded_records = nrow(working_age) - nrow(data)),
          "results/sample_audit.csv", row.names = FALSE)

# Population denominators include those outside the labor force.
monthly <- data |> group_by(YEAR, MONTH, education) |>
  summarise(population = sum(WTFINL), employed = sum(WTFINL * employed),
            unemployed = sum(WTFINL * unemployed),
            labor_force = sum(WTFINL * labor_force),
            sample_records = n(), .groups = "drop")
stopifnot(nrow(monthly) == 96)
annual <- monthly |> group_by(YEAR, education) |>
  summarise(across(c(population, employed, unemployed, labor_force), mean),
            .groups = "drop") |>
  mutate(unemployment_rate = 100 * unemployed / labor_force,
         participation_rate = 100 * labor_force / population,
         employment_ratio = 100 * employed / population)
stopifnot(all(abs(annual$employment_ratio - annual$participation_rate *
                   (1 - annual$unemployment_rate / 100)) < 1e-8))
write.csv(monthly, "results/monthly_totals.csv", row.names = FALSE)
write.csv(annual, "results/annual_rates.csv", row.names = FALSE)

plot_data <- annual |> mutate(education = factor(education, levels = rev(groups)),
                              year = factor(YEAR))
draw <- function(variable, title, subtitle, file) {
  p <- ggplot(plot_data, aes(x = .data[[variable]], y = education, color = year)) +
    geom_point(aes(shape = year), position = position_dodge(width = 0.45), size = 3) +
    geom_text(aes(label = sprintf("%.1f%%", .data[[variable]])),
              position = position_dodge(width = 0.45), hjust = -0.3, size = 3.5,
              show.legend = FALSE) +
    scale_color_manual(values = c("2019" = "#7A8793", "2024" = "#216B6B")) +
    scale_x_continuous(expand = expansion(mult = c(0.06, 0.18))) +
    labs(title = title, subtitle = subtitle, x = "Percent", y = NULL,
         color = NULL, shape = NULL,
         caption = "Source: IPUMS CPS, Basic Monthly; WTFINL weights. Annual averages, not seasonally adjusted.") +
    theme_minimal(base_size = 12) +
    theme(legend.position = "top", panel.grid.minor = element_blank(),
          panel.grid.major.y = element_blank(), plot.title.position = "plot",
          plot.caption = element_text(hjust = 0, size = 9))
  ggsave(file.path("results", file), p, width = 9, height = 5, dpi = 180, bg = "white")
}
draw("unemployment_rate", "Unemployment by education",
     "Unemployed as a share of the labor force, ages 25–64", "unemployment.png")
draw("participation_rate", "Who is in the labor force?",
     "Employed or unemployed as a share of civilians ages 25–64", "participation.png")
draw("employment_ratio", "How many adults have a job?",
     "Employed as a share of civilians ages 25–64", "employment.png")
capture.output(sessionInfo(), file = "results/session-info.txt")
print(annual)
