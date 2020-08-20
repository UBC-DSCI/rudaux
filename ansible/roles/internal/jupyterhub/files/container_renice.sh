#!/bin/bash
#
# Find the container which owns a particular process, identify the
# continare which owns it and (optionally) change the scheduling
# priority for the corresponding cgroup.
#
#######################################################################
# Arguments:
#  pid: The PID of a process running inside a docker container
#######################################################################

err() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')]: $@" >&2
  exit ${E_DID_NOTHING}
}

confirm() {
    # call with a prompt string or use a default
    read -r -p "${1:-Are you sure? [y/N]} " response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            true
            ;;
        *)
            false
            ;;
    esac
}

function get_cgroup_from_pid {
  if [ "$#" -ne 1 ] ; then
   echo "get_cgroup_from_pid called incorrectly ($#)"
   exit 1
  fi
  cgroup=$(head -n 1 /proc/${pid}/cgroup | cut -d: -f 3 | cut -d/ -f 3)
  if [[ "${PIPESTATUS[0]}" -ne 0 || "${PIPESTATUS[1]}" -ne 0 || "${PIPESTATUS[2]}" -ne 0 ]]; then
    cgroup=""
  fi
  echo "$cgroup"
}

function set_new_container_quota {
#####################################################################
# Arguments
#  period: current cfs_period_us value
#  quota: current cfs_quota_us value (optional, default is period)
#  new quota: new cfs_quota_us value (optional, default is quota / 2)
##################################################################### 
  if [ "$#" -lt 1 ] || [ "$#" -gt 4 ] ; then
   err "get_cgroup_from_pid called incorrectly ($#)"
  fi
  local cgroup period quota newquota
  cgroup="${1}"
  period="${2}"
  quota="${3:-${2}}"
  newquota="${4:-$((${3} / 2))}"

  quota_file="/sys/fs/cgroup/cpu/docker/${cgroup}/cpu.cfs_quota_us"
  local cmd="echo ${newquota} > /sys/fs/cgroup/cpu/docker/$cgroup/cpu.cfs_quota_us"
  echo "${cmd}"
  echo
  if [ -w "${quota_file}" ] ; then
    confirm "Change quota?" && eval "${cmd}"
  else
    echo "cgroup file not writable."
  fi 
}

main() {

  while getopts ":p:q:" opt; do
    case $opt in
      p)
        pid="${OPTARG}"
        ;;
      q)
        newquota="${OPTARG}"
        ;;
      \?)
        err "Invalid option: -$OPTARG" >&2
        ;;
    esac
  done     
 
  if [ -z "${pid}" ] ; then
    err "Usage $0 -p PID [-q QUOTA]"
  fi
 
  local cgroup 
  cgroup="$(get_cgroup_from_pid $pid)"
  if [ -z "${cgroup}" ] ; then
    err "Unable to idenfity parent container"
  else
    container_info=$(docker ps -f id="${cgroup}" --format "{{.ID}}: {{.Names}}")
    quota=$(</sys/fs/cgroup/cpu/docker/${cgroup}/cpu.cfs_quota_us)
    period=$(</sys/fs/cgroup/cpu/docker/${cgroup}/cpu.cfs_period_us)
    echo
    echo "[${container_info}] Current share: $quota/$period"
    echo


    set_new_container_quota ${cgroup} ${period} ${quota} ${newquota}
  fi
}


main "$@"
