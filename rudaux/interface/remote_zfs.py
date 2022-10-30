from typing import Dict, Optional, List
from rudaux.interface.base.submission_system import SubmissionSystem
from rudaux.model import Assignment, Student
from rudaux.model.document import Document
from rudaux.util.zfs import RemoteZFS
from rudaux.model.snapshot import parse_snapshot_name, Snapshot


class RemoteZFSSubmissions(SubmissionSystem):
    remote_zfs_hostname: str
    remote_zfs_port: str
    remote_zfs_username: str
    remote_zfs_tz: str
    remote_zfs_volume_pattern: str
    remote_zfs_collection_pattern: str
    remote_zfs_distribution_pattern: str
    remote_zfs_file_system_root: str
    zfs: Optional[RemoteZFS] = None

    class Config:
        arbitrary_types_allowed = True

    # ---------------------------------------------------------------------------------------------------
    def open(self):
        info = {"host": self.remote_zfs_hostname,
                "port": self.remote_zfs_port,
                "user": self.remote_zfs_username}
        self.zfs = RemoteZFS(info=info, tz=self.remote_zfs_tz)

    # ---------------------------------------------------------------------------------------------------
    def close(self):
        self.zfs.close()

    # ---------------------------------------------------------------------------------------------------
    def list_snapshots(self, assignments: Dict[str, Assignment],
                       students: Dict[str, Student]) -> List[Snapshot]:
        # TODO use remote_zfs_volume_pattern to get a volume string
        volume = self.remote_zfs_file_system_root
        'zfs_list to get folder structures'
        snap_dicts = self.zfs.get_snapshots(volume=volume)
        snapshots = [parse_snapshot_name(snap_dict["name"], assignments) for snap_dict in snap_dicts]
        return snapshots

    # ---------------------------------------------------------------------------------------------------
    def take_snapshot(self, snapshot: Snapshot):
        # TODO use remote_zfs_volume_pattern to get a volume string
        volume = self.remote_zfs_file_system_root
        self.zfs.take_snapshot(volume, snapshot.get_name())
        return

    # ---------------------------------------------------------------------------------------------------
    def collect_snapshot(self, snapshot: Snapshot):
        # TODO use remote_zfs_collection_pattern to read all the files
        # return document_info, document_data
        pass

    # ---------------------------------------------------------------------------------------------------
    def distribute(self, student: Student, document: Document):
        # TODO  use remote_zfs_distribution_pattern to decide what file to write and where
        """
        example: Send a feedback to student (write it there)
        Parameters
        ----------
        student
        document

        Returns
        -------

        """
        pass

    # ---------------------------------------------------------------------------------------------------


if __name__ == "__main__":
    from rudaux.model.settings import Settings
    from rudaux.flows import load_settings
    import importlib
    from rudaux.interface import LearningManagementSystem
    from rudaux.task.snap import get_pastdue_snapshots


    def get_class_from_string(s):
        module_name, class_name = s.rsplit(".", 1)
        return getattr(importlib.import_module(module_name), class_name)


    def get_learning_management_system(settings, group_name):
        LMS = get_class_from_string(settings.lms_classes[group_name])
        if not issubclass(LMS, LearningManagementSystem):
            raise ValueError
        lms = LMS.parse_obj(settings)
        return lms


    def get_submission_system(settings, group_name):
        SubS = get_class_from_string(settings.ss_classes[group_name])
        if not issubclass(SubS, SubmissionSystem):
            raise ValueError
        subs = SubS.parse_obj(settings)
        # TODO any additional runtime validation
        return subs


    # -----------------------------------------------------------------------

    _config_path = "/home/alireza/Desktop/SES/rudaux/rudaux_config.yml"
    _group_name = "course_dsci_100_test"
    _course_name = "section_dsci_100_test_01"

    settings = load_settings(_config_path)
    print(settings)
    settings = Settings.parse_obj(settings)
    print(settings)

    lms = get_learning_management_system(settings, group_name=_group_name)
    subs = get_submission_system(settings, group_name=_group_name)

    _course_info = lms.get_course_info(course_section_name=_course_name)
    _students = lms.get_students(course_section_name=_course_name)
    _assignments = lms.get_assignments(course_group_name=_group_name, course_section_name=_course_name)

    print('course_info: ', _course_info, '\n')
    print('students: ', _students, '\n')
    print('assignments: ', _assignments, '\n')

    subs.open()
    snapshots = subs.list_snapshots(assignments=_assignments, students=_students)
    print('snapshots: ', snapshots, '\n')

    import pendulum as plm
    from rudaux.model.course_info import CourseInfo


    def get_pastdue_snapshots(course_name: str, course_info: CourseInfo,
                              assignments: Dict[str, Assignment]) -> List[Snapshot]:
        """
        returns a list of snapshots which are past their due date

        Parameters
        ----------
        course_name: str
        course_info: CourseInfo
        assignments: Dict[str, Assignment]

        Returns
        -------
        pastdue_snaps: List[Snapshot]

        """
        pastdue_snaps = []

        for assignment_id, assignment in assignments.items():

            # if we are not past the assignment's due date yet, we skip
            if assignment.due_at > plm.now():
                print(f"Assignment {assignment.name} has future deadline {assignment.due_at}; skipping snapshot")

            # if the assignment's due date is before the course's start date, we skip
            elif assignment.due_at < course_info.start_at:
                print(
                    f"Assignment {assignment.name} deadline {assignment.due_at} "
                    f"prior to course start date {course_info.start_at}; skipping snapshot")

            # if we are past the assignment's due date, and it's after the course's start date,
            # we identify that as a pastdue snapshot
            else:
                print(f"Assignment {assignment.name} deadline {assignment.due_at} "
                            f"past due; adding snapshot to pastdue list")
                pastdue_snaps.append(Snapshot(course_name=course_name, assignment=assignment,
                                              override=None, student=None))

            for override_id, override in assignment.overrides.items():

                # if we are past the assignment's override's due date, we skip
                if override.due_at > plm.now():
                    print(
                        f"Assignment {assignment.name} override {override.name} "
                        f"has future deadline {override.due_at}; skipping snapshot")

                # if the assignment's override's due date is before course's start date, we skip
                elif override.due_at < course_info.start_at:
                    print(
                        f"Assignment {assignment.name} override {override.name} "
                        f"deadline {override.due_at} prior to course "
                        f"start date {course_info.start_at}; skipping snapshot")

                # if we are past the assignment's override's due date, and it's after the course's start date,
                # we identify that as a pastdue snapshot
                else:
                    print(
                        f"Assignment {assignment.name} override {override.name} deadline {override.due_at} past due; "
                        f"adding snapshot to pastdue list")
                    for student_id, student in override.students.items():
                        pastdue_snaps.append(Snapshot(course_name=course_name, assignment=assignment,
                                                      override=override, student=student))

        return pastdue_snaps


    pastdue_snaps = get_pastdue_snapshots(course_name=_group_name, course_info=_course_info, assignments=_assignments)
    print(pastdue_snaps)


    def get_existing_snapshots(course_name: str, course_info: CourseInfo,
                               assignments: Dict[str, Assignment], students: Dict[str, Student],
                               subs: SubmissionSystem) -> List[Snapshot]:

        existing_snaps = subs.list_snapshots(assignments=assignments, students=students)
        print(f"Found {len(existing_snaps)} existing snapshots.")
        print(f"Snapshots: {[snap.get_name() for snap in existing_snaps]}")
        return existing_snaps


    existing_snaps = get_existing_snapshots(course_name=_group_name, course_info=_course_info,
                                            assignments=_assignments, students=_students, subs=subs)

    print(existing_snaps)


