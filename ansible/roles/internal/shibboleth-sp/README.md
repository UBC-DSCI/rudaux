# Shibboleth-sp Role

This role will try to configure the host as a shibboleth service provider. This
involves installing the relevant packages, generating metadata and configuring a
shibboleth2.xml file. The role assumes that you alread have an Identity Provider
(IdP) in mind and have collected some of the details you will need. In
particular, it assumes that you have sensible values for the metadata of the IdP
and their connection endpoints. An example would be

Shibboleth relies on metadata exchanges between trusting parties and to prevent
disruption we use the "secret" mechanism to retain copies of generated metadata
files (keys and certificates). This allows us to rebuild machines without
forcing a reconfiguration of the IdP. The files are retained on the machine
running the ansible playbook and are stored under `{{ shib_secret }}` which
should be added to the list of "secret" directories created by that module. e.g.
set
```
secret: "{{ inventory_dir | realpath }}/.hostfiles/secret/{{ inventory_hostname }}"
secret_directories:
  - name: 'shib_secrets'
    path: 'shib'
```

Would result in files being stored in 
```
  ./.hostfiles/secret/{{ inventory_hostname }}/shib`
```

See the secret module for full details
