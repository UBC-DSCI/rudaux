from rudaux.interface.base.submission_system import SubmissionSystem
from rudaux.util.zfs import RemoteZFS


class RemoteZFSSubmissions(SubmissionSystem):
    remote_zfs_hostname : str
    remote_zfs_port : str
    remote_zfs_username : str
    remote_zfs_volume_pattern : str
    remote_zfs_collection_pattern : str
    remote_zfs_distribution_pattern : str

    def open(self):
        info = {"host" : self.remote_hostname,
                "port" : self.remote_zfs_port,
                "user" : self.remote_zfs_username}
        self.zfs = RemoteZFS(info = info)

    def close(self):
        self.zfs.close()

    def list_snapshots(self, assignments, students):
        snap_dicts = self.zfs.get_snapshots()
        # format of the snap_dicts
        #volume, remaining = line.split('@', 1)
        #name, remaining = remaining.split(' ', 1)
        #datetime = plm.from_format(remaining.strip(), 'ddd MMM D H:mm YYYY')
        #snaps.append( {'volume' : volume, 'name' : name, 'datetime':datetime} )
        return [parse_snapshot_name(snap_dict["name"], assignments, students) for snap_dict in snap_dicts]

    def take_snapshot(self, snapshot):
        volume = #TODO use remote_zfs_volume_pattern to get a volume string
        self.zfs.take_snapshot(volume, snapshot.get_name())
        return

    def collect_snapshot(self, snapshot):
        # TODO use remote_zfs_collection_pattern to read all the files
        #return document_info, document_data
        pass

    def distribute(self, student, document):
        # TODO  use remote_zfs_distribution_pattern to decide what file to write and where
        pass
