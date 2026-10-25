"""Regenerate the analysis, figures and article from the saved source extracts."""
from analyze import main as analyze
from plot_results import main as plot
from write_post import main as write

if __name__ == '__main__':
    analyze()
    plot()
    write()
