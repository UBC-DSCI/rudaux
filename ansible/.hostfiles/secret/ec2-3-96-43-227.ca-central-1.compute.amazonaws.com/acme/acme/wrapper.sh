#!/usr/bin/env bash
cd ~acme
sudo -u acme -- ./dehydrated --cron --config ./config.sh --ipv4 --accept-terms &> /dev/null
# Check for certificate newer than last restart
for c in certs/*/cert.pem; do
    [ "$c" -nt certs/.stamp ] && { RESTART=1; break; }
done
[ "$RESTART" = 1 ] && {
    sudo -u acme -- ./dehydrated --config ./config.sh --cleanup
    touch certs/.stamp
    systemctl restart httpd
    mailx -s "`hostname` Certificate renewed, server restarted" help@stat.ubc.ca </dev/null >&/dev/null
}
