# Dehydrate-letsencrypt

This module uses a [bash based acme
client](thttps://github.com/lukas2511/dehydrated) for the letsencrypt project to
provide secure SSL/TLS based web service for apache.

Where possible it will try to retain the certificate (and key) information
locally on the ansible client, this is intended to reduce disrupition and avoid
rate limits for the letsencrypt project. Their are security implications to
doing this (the ansible client MUST be secured).

This ansible role is likely to trigger some spurious changes. The main reason
for this is the sync described above. The wrapper runs daily as a cron job which
updates some of the information in the directory we are syncing. This could be
improved by being more selective in the sync.

## Dependencies
 - secret: An ansible module to retain some sensitive host details locally on
   the ansible client.
 - ansible-role-apache: A role to configure a basic apache server
