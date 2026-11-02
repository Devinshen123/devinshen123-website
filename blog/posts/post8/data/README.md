# Entirely simulated data

No external measurements are used. Recreate these files with `python code/analyze.py` from the post directory, using the settings and fixed stream order in `config.json`.

`original_sample.csv` contains the 50 original simulated fills. `simulation_inputs.npz` contains `sample`, `bootstrap_indices`, `coverage_samples`, and `null_samples`. The arrays provide the inputs for an independent audit of all saved results. See the post README for the statistical assumptions and denominators.
