"""Reproduce the article's calculations, checks, figures, and prose."""
from analyze import run as analyze
from verify import run as verify
from make_figures import run as figures
from write_post import run as article

if __name__ == "__main__":
    analyze()
    verify()
    figures()
    article()
