from app.main import create_app


def test_openapi_contains_the_phase_one_contract() -> None:
    schema = create_app().openapi()
    paths = set(schema["paths"])

    assert {
        "/v1/projects",
        "/v1/projects/{project_id}/tasks",
        "/v1/tasks/{task_id}",
        "/v1/tasks/{task_id}/cancel",
        "/v1/tasks/{task_id}/start",
        "/v1/tasks/{task_id}/retry",
        "/v1/tasks/{task_id}/events",
        "/v1/tasks/{task_id}/artifacts",
        "/v1/tasks/{task_id}/documents",
        "/v1/tasks/{task_id}/clarification",
        "/v1/tasks/{task_id}/engineering-brief",
        "/v1/tasks/{task_id}/viewer-manifest",
        "/v1/tasks/{task_id}/models/{artifact_id}/content",
    }.issubset(paths)

