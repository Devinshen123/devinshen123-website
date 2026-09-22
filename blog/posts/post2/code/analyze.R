# Run from blog/posts/post2: Rscript code/analyze.R
# No website requests: all analysis uses the saved CSV.
dir.create("results", showWarnings = FALSE)
jobs <- read.csv("data/jobs.csv", stringsAsFactors = FALSE, fileEncoding = "UTF-8")
stopifnot(nrow(jobs) > 0, !anyDuplicated(jobs$url),
          !anyNA(jobs$description), !anyNA(jobs$requirements))
text <- paste(jobs$description, jobs$requirements)
# Word boundaries avoid counting SQL inside NoSQL and R inside other words.
# Excel is case sensitive to avoid the ordinary verb "excel"; R is uppercase.
patterns <- c(SQL = "(?i)\\bSQL\\b", Excel = "\\bExcel\\b",
              Python = "(?i)\\bPython\\b", R = "\\bR\\b",
              Tableau = "(?i)\\bTableau\\b", `Power BI` = "(?i)\\bPower\\s*BI\\b")
flags <- sapply(patterns, function(p) grepl(p, text, perl = TRUE))
required_flags <- sapply(patterns, function(p) grepl(p, jobs$requirements, perl = TRUE))
counts <- data.frame(skill = names(patterns), jobs = colSums(flags),
                     percent = 100 * colMeans(flags),
                     requirements_section_jobs = colSums(required_flags), row.names = NULL)
counts <- counts[order(-counts$jobs, counts$skill), ]
write.csv(counts, "results/skill_counts.csv", row.names = FALSE)
write.csv(cbind(jobs[c("company", "title", "url")], flags),
          "results/job_skill_flags.csv", row.names = FALSE, fileEncoding = "UTF-8")

# Short contexts make it possible to review every keyword match.
audit <- do.call(rbind, lapply(names(patterns), function(skill) {
  do.call(rbind, lapply(seq_len(nrow(jobs)), function(i) {
    matches <- gregexpr(patterns[[skill]], text[i], perl = TRUE)[[1]]
    if (matches[1] < 0) return(NULL)
    data.frame(company = jobs$company[i], title = jobs$title[i], skill = skill,
               context = substring(text[i], pmax(1, matches - 70), matches + 100),
               url = jobs$url[i])
  }))
}))
write.csv(audit, "results/match_audit.csv", row.names = FALSE, fileEncoding = "UTF-8")
metrics <- c(sample_size = nrow(jobs), companies = length(unique(jobs$company)),
             sql_and_python = sum(flags[, "SQL"] & flags[, "Python"]),
             either_visualization = sum(flags[, "Tableau"] | flags[, "Power BI"]),
             remote = sum(jobs$workplace == "Remote"))
write.csv(data.frame(metric = names(metrics), value = unname(metrics)),
          "results/metrics.csv", row.names = FALSE)

# One simple chart, with both percentages and job counts.
png("results/skills.png", width = 1600, height = 960, res = 180)
par(mar = c(5, 6, 5, 3), family = "sans", bg = "white", col.axis = "#344054")
plot_counts <- counts[nrow(counts):1, ]
y <- barplot(plot_counts$percent, horiz = TRUE, names.arg = plot_counts$skill,
             las = 1, xlim = c(0, 115), axes = FALSE, border = NA,
             col = ifelse(plot_counts$skill == counts$skill[1], "#216B6B", "#A6C5C5"),
             xlab = "Share of sampled job postings mentioning the skill (%)")
axis(1, at = seq(0, 100, 20))
text(plot_counts$percent + 2, y,
     labels = sprintf("%.0f%% (%d/%d)", plot_counts$percent, plot_counts$jobs, nrow(jobs)),
     adj = 0, cex = 0.9, col = "#243746")
title("Which skills show up most often?", adj = 0, col.main = "#243746")
collection_date <- format(as.POSIXct(jobs$collected_at_utc[1], tz = "UTC"),
                          tz = "America/Los_Angeles", format = "%Y-%m-%d")
mtext(sprintf("%d DataAnalyst.com postings | %s (Pacific time)",
              nrow(jobs), collection_date),
      side = 3, line = 1, adj = 0, cex = 0.8, col = "#52616B")
dev.off()
capture.output(sessionInfo(), file = "results/session-info.txt")
print(counts, row.names = FALSE)
print(metrics)
