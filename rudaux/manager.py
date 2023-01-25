import fwirl
import pendulum as plm
from rudaux.fwirl_components.assets import AssignmentsListAsset, StudentsListAsset, \
    GradersListAsset, DeadlineAsset

from rudaux.fwirl_components.resources import LMSResource, SubmissionSystemResource, GradingSystemResource
from rudaux.fwirl_components.workers import SubmissionBuilder, GraderBuilder

from rudaux.flows import load_settings
from rudaux.model import Settings
from rudaux.task.learning_management_system import get_assignments, get_students, get_course_section_info
from rudaux.tasks import get_learning_management_system, get_submission_system, get_grading_system


# n_students = 10
# n_assignments = 5
# n_graders = 3
#
# list_of_assignments = [{'id': i, 'name': f'student_{i}'} for i in range(n_assignments)]
# list_of_students = [{'id': i, 'name': f'student_{i}'} for i in range(n_students)]
# list_of_graders = [{'id': i, 'name': f'student_{i}'} for i in range(n_graders)]


# ------------------------------------------------------------------------------------------------

def manager_run(config_path: str = '../rudaux_config.yml'):
    # config_path = '../rudaux_config.yml'
    course_name = 'course_dsci_100_test'
    course_section_name = 'section_dsci_100_test_01'
    settings = load_settings(config_path)

    lms = get_learning_management_system(settings=settings, group_name=course_name)
    submission_sys = get_submission_system(settings=settings, group_name=course_name)
    submission_sys.open(course_name=course_name)
    grading_sys = get_grading_system(settings=settings, group_name=course_name)

    # ----------------------------------------------

    graph = fwirl.AssetGraph("rudaux_graph")

    grader_account_assets = dict()
    deadline_assets = dict()
    submission_raw_assets = dict()
    submission_cleaned_assets = dict()
    submission_auto_graded_assets = dict()
    submission_manually_graded_assets = dict()
    generated_feedback_assets = dict()
    returned_feedback_assets = dict()
    uploaded_grade_assets = dict()
    returned_solution_assets = dict()

    lms_resource = LMSResource(key=0, settings=settings, course_name=course_name, min_query_interval=10)
    # grading_system_resource = GradingSystemResource(key=0)
    # submission_system_resource = SubmissionSystemResource(key=0)

    course_section_info = lms_resource.get_course_section_info(course_section_name=course_section_name)
    students = lms_resource.get_students(course_section_name=course_section_name)
    assignments = lms_resource.get_assignments(course_section_name=course_section_name)

    course_section_names = settings.course_groups[course_name]
    selected_assignments = settings.assignments[course_name]

    print('course_section_info: ', course_section_info)
    # print('students: ', students)
    # print('assignments: ', assignments)
    print('course_section_names: ', course_section_names)
    print('selected_assignments: ', selected_assignments)

    min_polling_interval = 1

    assignments_list_asset = AssignmentsListAsset(
        key=f"AssignmentsList", dependencies=[], lms_resource=lms_resource,
        min_polling_interval=min_polling_interval, course_section_name=course_section_name)

    students_list_asset = StudentsListAsset(
        key=f"AssignmentsList", dependencies=[], lms_resource=lms_resource,
        min_polling_interval=min_polling_interval, course_section_name=course_section_name)

    submission_builder = SubmissionBuilder(
        assignments_list_asset=assignments_list_asset,
        students_list_asset=students_list_asset,
        lms_resource=lms_resource)

    graph.workers.append(submission_builder)

    # graders_list_asset = GradersListAsset(
    #     key=f"GradersListAsset",
    #     dependencies=[],
    #     resources=[grading_system_resource],
    #     group=0,
    #     subgroup=0)

    # SubmissionBuilder(watched_assets=[assignments_list_asset, students_list_asset, graders_list_asset])
    # GraderBuilder(watched_assets=[students_list_asset, graders_list_asset])

    for assignment_id, assignment in assignments.items():
        print(assignment)

        # -----------------------------------------------------------------------------
        # # dependencies: uploaded_grade_asset -> submission_manually_graded_asset
        # submitted_fraction_asset = SubmittedFractionAsset(
        #     key=f"SubmittedFraction_A{assignment_id}",
        #     dependencies=[],
        #     resources=[submission_system_resource],
        #     group=assignment_id,
        #     subgroup=0)
        #
        # uploaded_grade_assets[f"A{assignment_id}"] = submitted_fraction_asset
        # -----------------------------------------------------------------------------

        # for grader in list_of_graders:
        #     grader_id = grader['id']
        #
        #     # dependencies: grader_account_asset ->
        #     grader_account_asset = GraderAccountAsset(
        #         key=f"GraderAccount_A{assignment_id}",
        #         dependencies=[],
        #         resources=None,
        #         group=assignment_id,
        #         subgroup=grader_id)
        #
        #     grader_account_assets[f"A{assignment_id}_G{grader_id}"] = grader_account_asset

        # -----------------------------------------------------------------------------

        for student_id, student in students.items():
            print(student)

            # -----------------------------------------------------------------------------
            # dependencies: deadline_asset -> []
            # deadline_asset = DeadlineAsset(
            #     key=f"Deadline_A{assignment_id}_S{student_id}",
            #     dependencies=[],
            #     lms_resource=lms_resource,
            #     student=student,
            #     assignment=assignment
            # )
            #
            # deadline_assets[f"A{assignment_id}_S{student_id}"] = deadline_asset

            # -----------------------------------------------------------------------------
            # # dependencies: submission_asset -> deadline_asset
            # submission_raw_asset = SubmissionRawAsset(
            #     key=f"SubmissionRaw_A{assignment_id}_S{student_id}",
            #     dependencies=[deadline_asset],
            #     resources=[submission_system_resource],
            #     group=assignment_id,
            #     subgroup=student_id)
            #
            # submission_raw_assets[f"A{assignment_id}_S{student_id}"] = submission_raw_asset

            # -----------------------------------------------------------------------------
            # # dependencies: submission_cleaned_asset -> submission_asset
            # submission_cleaned_asset = SubmissionCleanedAsset(
            #     key=f"SubmissionCleaned_A{assignment_id}_S{student_id}",
            #     dependencies=[submission_raw_asset],
            #     resources=None,
            #     group=assignment_id,
            #     subgroup=student_id)
            #
            # submission_cleaned_assets[f"A{assignment_id}_S{student_id}"] = submission_cleaned_asset

            # -----------------------------------------------------------------------------
            # # dependencies: submission_auto_graded_asset -> submission_cleaned_asset
            # submission_auto_graded_asset = SubmissionAutoGradedAsset(
            #     key=f"SubmissionAutoGraded_A{assignment_id}_S{student_id}",
            #     dependencies=[submission_cleaned_asset],
            #     resources=None,
            #     group=assignment_id,
            #     subgroup=student_id)
            #
            # submission_auto_graded_assets[f"A{assignment_id}_S{student_id}"] = submission_auto_graded_asset

            # -----------------------------------------------------------------------------
            # # dependencies: submission_manually_graded_asset -> submission_auto_graded_asset
            # submission_manually_graded_asset = SubmissionManuallyGradedAsset(
            #     key=f"SubmissionManuallyGraded_A{assignment_id}_S{student_id}",
            #     dependencies=[submission_auto_graded_asset],
            #     resources=None,
            #     group=assignment_id,
            #     subgroup=student_id)
            #
            # submission_manually_graded_assets[f"A{assignment_id}_S{student_id}"] = submission_manually_graded_asset

            # -----------------------------------------------------------------------------
            # # dependencies: generated_feedback_asset -> submission_manually_graded_asset
            # generated_feedback_asset = GeneratedFeedbackAsset(
            #     key=f"GeneratedFeedback_A{assignment_id}_S{student_id}",
            #     dependencies=[submission_manually_graded_asset],
            #     resources=None,
            #     group=assignment_id,
            #     subgroup=student_id)
            #
            # generated_feedback_assets[f"A{assignment_id}_S{student_id}"] = generated_feedback_asset

            # -----------------------------------------------------------------------------
            # # dependencies: returned_feedback_asset -> generated_feedback_asset
            # returned_feedback_asset = ReturnedFeedbackAsset(
            #     key=f"ReturnedFeedback_A{assignment_id}_S{student_id}",
            #     dependencies=[generated_feedback_asset],
            #     resources=None,
            #     group=assignment_id,
            #     subgroup=student_id)
            #
            # returned_feedback_assets[f"A{assignment_id}_S{student_id}"] = returned_feedback_asset

            # -----------------------------------------------------------------------------
            # # dependencies: uploaded_grade_asset -> submission_manually_graded_asset
            # uploaded_grade_asset = UploadedGradeAsset(
            #     key=f"GeneratedFeedback_A{assignment_id}_S{student_id}",
            #     dependencies=[submission_manually_graded_asset],
            #     resources=None,
            #     group=assignment_id,
            #     subgroup=student_id)
            #
            # uploaded_grade_assets[f"A{assignment_id}_S{student_id}"] = uploaded_grade_asset

            # -----------------------------------------------------------------------------
            # # dependencies: returned_solution_asset -> [deadline_asset, submitted_fraction_asset]
            # returned_solution_asset = ReturnedSolutionAsset(
            #     key=f"ReturnedSolution_A{assignment_id}_S{student_id}",
            #     dependencies=[deadline_asset, submitted_fraction_asset],
            #     resources=None,
            #     group=assignment_id,
            #     subgroup=student_id)
            #
            # returned_solution_assets[f"A{assignment_id}_S{student_id}"] = returned_solution_asset

            # -----------------------------------------------------------------------------

            # -----------------------------------------------------------------------------

    # g.add_assets(list(grader_account_assets.values()))
    # graph.add_assets(list(deadline_assets.values()))
    # g.add_assets(list(submission_raw_assets.values()))
    # g.add_assets(list(submission_cleaned_assets.values()))
    # g.add_assets(list(submission_auto_graded_assets.values()))
    # g.add_assets(list(submission_manually_graded_assets.values()))
    # g.add_assets(list(generated_feedback_assets.values()))
    # g.add_assets(list(returned_feedback_assets.values()))
    # g.add_assets(list(uploaded_grade_assets.values()))
    # g.add_assets(list(returned_solution_assets.values()))

    graph.summarize()
    print("refresh")
    input()


if __name__ == '__main__':
    manager_run()
