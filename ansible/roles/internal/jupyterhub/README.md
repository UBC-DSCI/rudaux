# JupyterHub Role

This is the central role for the jupyter.yml play. It contains a lot of
(conditional) dependencies, mostly for auth, and then tries to construct a valid
jupyterhub_config.py.
