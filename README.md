
# AEDS 6400 Blog

Quarto website published through GitHub Pages from `main` / `docs`.

- [Blog Post 1](https://devinshen123.github.io/devinshen123-website/blog/posts/post1/): interpreting p-values.
- [Blog Post 2](https://devinshen123.github.io/devinshen123-website/blog/posts/post2/): R web scraping and data analyst skill mentions.
- [Blog Post 3](https://devinshen123.github.io/devinshen123-website/blog/posts/post3/): weighted IPUMS CPS visualizations of education and employment.

For Blog Post 2's code, data, results, and replication instructions, see [the project README](blog/posts/post2/README.md).

For Blog Post 3's R code, aggregate results, IPUMS data instructions, and weighting method, see [its project README](blog/posts/post3/README.md). Raw CPS microdata are excluded from this public repository.

To build the site, install Quarto and run `quarto render` from this directory. Blog Post 2 also needs R plus `knitr` and `rmarkdown` for its inline results; use the package installation instructions in its README. Rendering does not scrape websites.
