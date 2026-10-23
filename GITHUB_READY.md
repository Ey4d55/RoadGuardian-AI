# GitHub preparation

This workspace is prepared for source review and upload. The public repository is Ey4d55/RoadGuardian-AI. Pages publishes main:/docs; dist is excluded. The preparation script itself never uploads.

## What goes into the repository

Python source and tests, ESP32 firmware, synthetic events, local UI assets and font license, example calibration files, documentation, and the CI workflow. `package_release.py` uses an explicit allowlist and creates a verified ZIP for review.

## What stays local

Camera frames (including the last frame in `edge_status.json`), phone photos, remote attachments, training datasets, model weights, dependencies, scratch files, secrets and machine-specific `road_region.json`. `.gitignore` excludes them. Do not force-add ignored files.

## Before upload

1. Read `ACCEPTANCE_REVIEW.md` for the tested scope and remaining hardware work.
2. Run `python review_project.py`, then `python package_release.py`.
3. Inspect `git status --short` and the ZIP content. Keep your own camera calibration local.
4. Choose the repository owner/name and visibility, then add the remote and push. Do not run `git add -f` on photos or datasets.

No project-wide redistribution license has been chosen here. Third-party notices remain in `THIRD_PARTY_NOTICES.md` and `assets/FONT-LICENSE.txt`. Check dependency and model terms when choosing the project's license or distributing model weights.

CI tests use fake camera/serial devices and the dashboard dependencies; they do not access a real camera, flash an ESP32, measure object detection accuracy or download YOLO weights.
