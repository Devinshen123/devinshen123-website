# Run from blog/posts/post2: Rscript code/scrape.R
# Default: reuse saved HTML. --live downloads into a NEW dated snapshot folder.
library(rvest)
dir.create("data/raw", recursive = TRUE, showWarnings = FALSE)
live <- "--live" %in% commandArgs(trailingOnly = TRUE)
cache <- if (live) file.path("data", paste0("snapshot-", format(Sys.time(), "%Y%m%d-%H%M%S"))) else "data/raw"
dir.create(cache, recursive = TRUE, showWarnings = FALSE)
base_url <- "https://www.dataanalyst.com"
listing_url <- paste0(base_url, "/job-experience/entry-level-data-analyst-jobs")

# Three seconds between requests; no retries or access restriction workarounds.
get_page <- function(url, name) {
  path <- file.path(cache, name)
  if (file.exists(path)) return(read_html(path))
  if (!live) stop("Saved HTML missing: restore data/raw or use --live after reviewing site rules.")
  Sys.sleep(3)
  message("Reading ", url)
  page <- read_html(url)
  xml2::write_html(page, path)
  page
}

# Check this small site's robots rules before any new collection.
if (live) {
  rules <- readLines(paste0(base_url, "/robots.txt"), warn = FALSE)
  writeLines(rules, file.path(cache, "robots.txt"))
  disallow <- grep("^Disallow:", rules, value = TRUE, ignore.case = TRUE)
  if (any(nzchar(trimws(sub("^[^:]+:", "", disallow))))) {
    stop("Robots rules changed: review them before collecting any job pages.")
  }
  writeLines(format(Sys.time(), tz = "UTC", usetz = TRUE), file.path(cache, "collected_at.txt"))
}

page <- get_page(listing_url, "listing.html")
cards <- html_elements(page, "a.cms-jobs-counter")
field <- function(selector) html_text2(html_element(cards, selector))
jobs <- data.frame(
  title = trimws(field("h3")), company = trimws(field(".card-link-home")),
  location = field(".card-job-category-wrapper-location .card-job-category-text"),
  workplace = field(".card-job-category-wrapper-workplace .card-job-category-text"),
  experience = field(".card-job-category-wrapper-experience .card-job-category-text"),
  published = field(".card-job-category-wrapper-published .card-job-category-text"),
  status = field(".card-job-category-text-expired"),
  url = xml2::url_absolute(html_attr(cards, "href"), base_url)
)
stopifnot(nrow(jobs) > 0, !anyNA(jobs$title), !anyNA(jobs$url))
# Define the sample before reading skill frequencies: first 50 matching cards,
# in the site's displayed order, on this single listing page. No pagination.
jobs$eligible <- jobs$experience == "0 - 3 years" & jobs$status == "Active" &
  grepl("data analyst", jobs$title, ignore.case = TRUE) &
  !grepl("\\b(senior|sr|lead|principal|manager|director)\\b", jobs$title, ignore.case = TRUE)
jobs$eligible[is.na(jobs$eligible)] <- FALSE
write.csv(jobs, "data/listing_audit.csv", row.names = FALSE, fileEncoding = "UTF-8")
jobs <- jobs[jobs$eligible & !duplicated(jobs$url) &
               !duplicated(paste(tolower(jobs$company), tolower(jobs$title), jobs$location)), ]
jobs <- head(jobs, 50)
jobs$eligible <- NULL
jobs$description <- jobs$requirements <- NA_character_
for (i in seq_len(nrow(jobs))) {
  slug <- sub(".*/", "", jobs$url[i])
  detail <- get_page(jobs$url[i], paste0(slug, ".html"))
  # Only responsibilities and requirements; exclude company bios and related jobs.
  jobs$description[i] <- html_text2(html_element(detail, ".rich-text-block-3"))
  jobs$requirements[i] <- html_text2(html_element(detail, ".rich-text-block-4"))
  if (is.na(jobs$description[i]) || is.na(jobs$requirements[i]) ||
      nchar(jobs$description[i]) + nchar(jobs$requirements[i]) < 100) {
    stop("Missing job text: inspect ", jobs$url[i])
  }
}
jobs$collected_at_utc <- readLines(file.path(cache, "collected_at.txt"), warn = FALSE)[1]
write.csv(jobs, "data/jobs.csv", row.names = FALSE, fileEncoding = "UTF-8")
message("Saved ", nrow(jobs), " jobs; cache: ", cache)
