"""Operator designation, independent of native completion status."""

RESULT_POLICY_ID = 'functionality-tests-until-explicit-release'


def result_designation():
    """Metadata for new records; historical acquisition files remain unchanged."""
    return {'result_policy_id': RESULT_POLICY_ID,
            'result_classification': 'FUNCTIONALITY_TEST',
            'publication_eligible': False, 'runtime_calibration_eligible': False}
