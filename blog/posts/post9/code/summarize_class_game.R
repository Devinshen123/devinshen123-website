# Summarize the instructor's paired final portfolio values without copying rows.
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 2L)
game <- readxl::read_excel(args[[1]])
stopifnot(all(c("portfolio1", "portfolio2") %in% names(game)))
x <- as.numeric(game$portfolio1)
y <- as.numeric(game$portfolio2)
keep <- complete.cases(x, y)
x <- x[keep]
y <- y[keep]
delta <- y - x
write.csv(data.frame(pairs = length(delta), intuition_mean_usd = mean(x),
                     indicator_mean_usd = mean(y), paired_mean_gain_usd = mean(delta),
                     indicator_ahead = sum(delta > 0), intuition_ahead = sum(delta < 0),
                     tied = sum(delta == 0)), args[[2]], row.names = FALSE)
