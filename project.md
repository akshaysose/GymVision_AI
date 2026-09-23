# AI Real-time GYM Coach

## 1. Project Purpose

AI Real-time GYM Coach is a Streamlit application that uses a webcam to analyze exercise form in real time. It detects body landmarks with MediaPipe, calculates exercise-specific angles and posture states, counts repetitions, tracks sets, stores workout history in SQLite, and optionally gives spoken coaching through Gemini and Google Text-to-Speech.

Supported exercises:

- Squats
- Push-ups
- Biceps Curls (Dumbbell)
- Shoulder Press
- Lunges

The application is designed as a browser-based workout assistant. The browser supplies camera frames through WebRTC, while Python performs pose processing and updates the Streamlit interface.

## 2. High-Level Architecture

```text
Browser camera
    |
    v
streamlit-webrtc
    |
    v
VideoProcessorClass
    |
    +--> MediaPipe Pose Landmarker
    |
    +--> Exercise detector
            |
            +--> angles, posture, repetition count

Streamlit rerun
    |
    v
sync_metrics_update
    |
    +--> session state
    +--> set and workout completion
    +--> SQLite workout history
    +--> VoicePipeline
            |
            +--> Gemini text coaching
            +--> gTTS audio
```

The main application is event-driven by Streamlit reruns. The WebRTC processor continuously handles video frames, while the Streamlit script reads the latest processor metrics during reruns.

## 3. Repository Structure

```text
ai-gym-coach/
|-- README.md
|-- project.md
|-- .gitignore
|-- Main App/
    |-- main.py
    |-- requirements.txt
    |-- packages.txt
    |-- .env                  # local secret, ignored by git
    |-- .env.example          # safe configuration template
    |-- core/
    |-- detectors/
    |-- ml_models/
    |-- pages/
    |-- services/
    |-- static/
    |-- tutorial-info/
```

## 4. Root Files

### `README.md`

The short project readme. It currently contains the project title and can be expanded with setup instructions if needed.

### `project.md`

This document. It explains the project purpose, architecture, runtime flow, responsibilities of each file, and operational notes.

### `.gitignore`

Prevents local and generated content from being committed, including:

- Python cache files
- Virtual environments
- `.env` secrets
- Local SQLite database
- Log files

The real API key must stay in `Main App/.env` or in a deployment secret manager. Never commit it.

## 5. Main App Files

### `Main App/main.py`

This is the application entry point and Streamlit page controller.

Startup responsibilities:

1. Load environment variables with `python-dotenv`.
2. Configure the Streamlit page.
3. Load the custom CSS and font.
4. Initialize the SQLite database.
5. Display the login wall until a username is available.
6. Initialize the Gemini client, LLM coach, TTS service, and voice pipeline.

Sidebar responsibilities:

- Select the exercise.
- Select target sets and repetitions per set.
- Start or end a workout.
- Display total repetitions.
- Display current set progress.
- Display exercise-specific metrics.

Main page responsibilities:

- Display the application title and coaching feedback.
- Display the WebRTC camera component during an active workout.
- Synchronize video metrics into Streamlit state.
- Display grouped workout history.
- Display the author footer.

The application must normally be started from the `Main App` directory because assets and the MediaPipe model are resolved using the current working directory.

### `Main App/requirements.txt`

Python dependencies used by the application:

- `streamlit`: web UI and application reruns.
- `streamlit-webrtc`: camera and WebRTC video processing.
- `mediapipe`: pose landmark detection.
- `opencv-python-headless`: frame manipulation and drawing overlays.
- `pandas`: workout history formatting and grouping.
- `google-genai`: Gemini API client.
- `gtts`: text-to-speech generation.
- `python-dotenv`: loading `GEMINI_API_KEY` from `.env`.

### `Main App/packages.txt`

System packages used by Linux-based deployments such as Streamlit Community Cloud. They provide graphics and shared libraries needed by OpenCV and MediaPipe.

### `Main App/.env`

Local configuration file. It contains:

```text
GEMINI_API_KEY=your-key-here
```

This file is ignored by git. The key should be rotated immediately if it is exposed publicly.

### `Main App/.env.example`

Safe template showing the required environment variable without containing a real credential.

## 6. Core Package

### `core/__init__.py`

Marks `core` as a Python package.

### `core/base_exercise.py`

Defines the common base class for all exercise detectors.

`BaseExercise` provides:

- `reps`: current repetition count.
- `stage`: movement phase, such as `up` or `down`.
- `calculate_angle(a, b, c)`: calculates the angle at point `b` using three 2D points.
- `get_point(landmarks, idx)`: converts a MediaPipe landmark to an `(x, y)` tuple.
- Abstract `process()` and `reset()` methods.

The angle calculation uses the dot-product formula. The cosine value is clamped between `-1` and `1` before calling `acos`, preventing floating-point errors.

## 7. Exercise Detectors

Every detector receives MediaPipe pose landmarks and returns a dictionary of metrics. Repetition counting uses a state machine:

1. Detect a movement threshold and set the stage.
2. Detect the return threshold while the stage is active.
3. Increment `reps` once.

This prevents multiple counts while the user remains in one position.

### `detectors/squat.py`

`SquatDetector`:

- Calculates the selected knee angle.
- Selects the side with the better knee landmark visibility.
- Uses hip, knee, and ankle visibility checks.
- Enters `down` below the down threshold.
- Counts a rep when the knee returns above the up threshold.
- Calculates back angle using shoulder, hip, and knee.
- Reports `GOOD DEPTH`, `TOO HIGH`, `STANDING`, or `N/A`.

Returned metrics:

```text
reps
knee_angle
back_angle
depth_status
```

### `detectors/pushup.py`

`PushUpDetector`:

- Selects the arm with better elbow visibility.
- Calculates elbow angle for movement tracking.
- Calculates shoulder-hip-ankle body angle.
- Estimates hip deviation from the shoulder-to-ankle midpoint.
- Counts a rep after a down-to-up transition.
- Reports body alignment and whether the hips are level, sagging, or piked.

Returned metrics:

```text
reps
elbow_angle
body_alignment
hip_status
```

### `detectors/biceps_curl.py`

`BicepsCurlDetector`:

- Selects the arm with better elbow visibility.
- Calculates shoulder-elbow-wrist angle.
- Counts a rep after an up-to-down transition.
- Measures elbow drift from the shoulder's x-position.
- Measures torso swing using the angle between the shoulder midpoint and hip midpoint.

Returned metrics:

```text
reps
elbow_angle
shoulder_status
swing_status
```

### `detectors/shoulder_press.py`

`ShoulderPressDetector`:

- Selects the arm with better elbow visibility.
- Uses a high elbow angle as the extended phase.
- Counts a rep when the elbow returns below the down threshold.
- Reports extension quality.
- Calculates shoulder-hip-knee back angle to detect excessive arching.

Returned metrics:

```text
reps
elbow_angle
extension_status
back_arch_status
```

### `detectors/lunges.py`

`LungesDetector`:

- Calculates both knee angles.
- Treats the smaller knee angle as the front leg.
- Counts a rep after a down-to-up transition.
- Calculates torso angle.
- Compares shoulder midpoint and hip midpoint to estimate balance.

Returned metrics:

```text
reps
front_knee_angle
torso_angle
balance_status
```

### `detectors/__init__.py`

Marks `detectors` as a Python package.

## 8. Machine Learning Model

### `ml_models/pose_landmarker_full.task`

The MediaPipe pose landmark model used by `VideoProcessorClass`. It identifies body landmarks such as shoulders, elbows, wrists, hips, knees, and ankles.

### `ml_models/__init__.py`

Marks the model directory as a Python package directory.

## 9. Services

### `services/__init__.py`

Marks `services` as a Python package.

### `services/auth/login_wall.py`

Implements the simple username-based session gate.

Behavior:

1. If `user_id` is already in Streamlit session state, allow the application to continue.
2. Otherwise, display a login form.
3. Reject an empty username.
4. Create or retrieve the user from SQLite.
5. Store `user_id` and `username` in session state.
6. Rerun the app after successful login.

This is identity tracking, not password authentication.

### `services/state/session_defaults.py`

Initializes Streamlit session-state values only when they do not already exist.

It contains:

- Workout plan values.
- Repetition and set counters.
- Current angles.
- Form status values.
- Coaching notification flags.
- Persistence timing values.

Keeping defaults in one place prevents missing-key errors during the first page render.

### `services/config/workout_config.py`

Stores shared configuration:

- Supported exercise names.
- MediaPipe pose connection pairs used to draw the skeleton.
- The metrics expected by each exercise.
- The system prompt sent to Gemini.

`METRICS_FIELDS` is used by `sync_metrics_update` to copy detector values into the correct Streamlit state keys.

### `services/vision/exercise_video_processor.py`

Owns real-time frame processing.

Initialization:

1. Load `pose_landmarker_full.task`.
2. Create a MediaPipe `PoseLandmarker` in video mode.
3. Create one detector instance for each supported exercise.
4. Prepare a lock-protected metrics field.

For each frame:

1. Convert the WebRTC frame to a NumPy/OpenCV image.
2. Flip the image horizontally for a mirror-camera experience.
3. Convert the image to a MediaPipe image.
4. Advance the video timestamp.
5. Run pose landmark detection.
6. If a pose exists, draw the skeleton and call the selected detector.
7. Add `pose_detected=True` and save the latest metrics.
8. If no pose exists, draw a warning and save `pose_detected=False`.
9. Return the annotated frame to the browser.

A thread lock protects metrics because the WebRTC processing thread and Streamlit thread access the processor independently.

### `services/tracking/metrics.py`

Bridges the video processor and the Streamlit application.

`sync_metrics_update(context)`:

1. Confirms that WebRTC is active.
2. Gets the current video processor.
3. Sets the selected exercise on the processor.
4. Reads the latest detector metrics.
5. Copies repetitions and exercise-specific values into session state.
6. Calculates completed sets using integer division:

```text
sets_completed = reps // reps_per_set
current_set_reps = reps % reps_per_set
```

7. Detects workout completion when completed sets reach the target.
8. Saves newly completed sets to SQLite.
9. Sends set-completed and workout-completed coaching events.
10. Sends no-pose and ongoing-form events when applicable.

The function tracks `last_saved_sets_completed` so the same set is not saved repeatedly.

### `services/persistence/exercise_repository.py`

Provides SQLite persistence.

Database location:

```text
Main App/data.db
```

Tables:

`users`

- `id`
- `username`
- `created_at`

`exercises`

- `id`
- `user_id`
- `exercise_name`
- `reps`
- `sets`
- `time`
- `created_at`

Important functions:

- `_get_connection()`: creates a cached SQLite connection.
- `init_db()`: creates tables if they do not exist.
- `get_user()`: finds a user by username.
- `create_user()`: inserts a new user.
- `get_or_create_user()`: login helper.
- `add_exercise()`: inserts or updates today's exercise summary.
- `get_users_exercises()`: loads history for one user.

The application groups history by exercise and date before displaying it.

### `services/coaching/llm.py`

Wraps the Gemini client in `LLMCoach`.

For each event it:

1. Builds an event prompt.
2. Adds the detected form issue when one exists.
3. Includes recent coaching history.
4. Sends the request to Gemini model `gemini-3.6-flash`.
5. Applies the shared coaching system instruction.
6. Extracts the generated text.
7. Stores the assistant response in recent history.

The coach is used for short spoken-style responses rather than long explanations.

### `services/coaching/voice_pipeline.py`

Coordinates form issue selection, Gemini text generation, and speech generation.

`_find_form_issue()` converts raw exercise metrics into a short coaching issue. Examples:

- Squat too shallow.
- Squat back leaning too far forward.
- Push-up body alignment is poor.
- Curl torso is swinging.
- Shoulder press has excessive back arch.
- Lunge balance is poor.

`process_event()` applies two protections:

- Normal ongoing form coaching is limited to one request every five seconds.
- Gemini errors pause further requests temporarily. A quota error pauses coaching for 60 seconds, while other provider errors pause it for 15 seconds.

If Gemini fails, it returns `None` instead of crashing the workout. Rep counting, metrics, and persistence continue.

`autoplay_audio()` hides the Streamlit audio widget and attempts browser autoplay for generated coaching audio.

### `services/coaching/tts.py`

Uses gTTS to convert Gemini text into MP3 bytes stored in memory. The bytes are passed to Streamlit audio playback without creating a permanent audio file.

### `services/ui/style_loader.py`

Loads visual styles:

- `load_css()`: injects `static/style.css`.
- `inject_local_font()`: embeds `AdobeClean.otf` as a base64 web font.
- `inject_webrtc_styles()`: injects matching styles into the WebRTC iframe.

### `services/vision/__init__.py`

Marks the vision service directory as a Python package.

### Empty package initializers

The `__init__.py` files in `services/auth`, `services/coaching`, `services/config`, `services/persistence`, `services/state`, `services/tracking`, and `services/ui` make those directories importable Python packages.

## 10. Static Assets

### `static/style.css`

Defines the dark application theme, typography, zero-radius controls, metric cards, forms, tables, buttons, and the author footer.

### `static/AdobeClean.otf`

Local font embedded into the Streamlit page and WebRTC iframe.

## 11. Pages and Tutorial Files

### `pages/__init__.py`

Marks the pages directory as a Python package. The current UI is primarily implemented in `main.py`; there are no additional Streamlit page scripts at present.

### `tutorial-info/v*.txt`

Historical tutorial or implementation notes from different project versions. They are reference material and are not part of the current runtime import path.

## 12. Complete Runtime Flow

### A. Application startup

1. Run Streamlit from `Main App`.
2. Python imports the application modules.
3. `load_dotenv()` loads `GEMINI_API_KEY`.
4. Static CSS and font assets are loaded.
5. SQLite tables are initialized.
6. The login screen is shown if the session has no user.

### B. Login

1. The user enters a username.
2. The repository searches for that username.
3. A new user is inserted when necessary.
4. The user identity is saved in Streamlit session state.
5. The page reruns and shows the workout controls.

### C. Start workout

1. The user selects an exercise, set count, and reps per set.
2. The values are copied into session state.
3. Counters and timing values are reset.
4. A `workout_started` coaching event may be sent.
5. The page reruns with the camera component.

### D. Camera and pose processing

1. The browser grants camera permission.
2. WebRTC sends frames to `VideoProcessorClass`.
3. MediaPipe detects landmarks.
4. The selected detector calculates angles and status values.
5. The detector updates its internal repetition state.
6. The processor draws the skeleton and status overlay.
7. The latest metrics are stored for Streamlit.

### E. Streamlit synchronization

1. `sync_metrics_update()` reads the latest metrics.
2. Session-state metrics update the sidebar.
3. Repetition count is converted to set progress.
4. Newly completed sets are saved to SQLite.
5. Coaching events are sent when allowed.
6. Streamlit reruns while the WebRTC stream is playing.

### F. Coaching

1. Raw metrics are translated into a form issue.
2. Gemini generates a short coaching sentence.
3. gTTS converts the sentence to MP3 bytes.
4. Streamlit renders the audio for browser playback.
5. API quota failures are shown as warnings and do not stop tracking.

### G. Workout history

1. The current user's rows are loaded from SQLite.
2. Dates are converted to date values.
3. Rows are grouped by exercise and date.
4. Reps, sets, and time are summed.
5. The result is displayed as a Streamlit table.

## 13. Running the Project

From PowerShell:

```powershell
Set-Location "C:\Users\aksha\Desktop\ai-gym-coach\Main App"
python -m pip install -r requirements.txt
python -m streamlit run main.py --server.headless true --server.port 8502
```

Open:

```text
http://localhost:8502
```

Required configuration:

```text
GEMINI_API_KEY=your-gemini-api-key
```

The browser must allow camera access for exercise analysis. Gemini coaching also requires an active API key and available quota.

## 14. State and Data Model

Streamlit session state stores temporary per-browser-session values. Important values include:

```text
user_id
username
exercise_type
workout_started
target_sets
reps_per_set
reps
sets_completed
current_set_reps
exercise-specific angles and statuses
voice_pipeline
coach_feedback
audio_to_play
```

SQLite stores durable user and workout history. The detector instances store their current movement stage and repetition count in memory.

## 15. External Services and Failure Behavior

### MediaPipe

Used locally for pose inference. If the model file is missing or incompatible, camera processing cannot initialize.

### Gemini

Used only for natural-language coaching. If the key is missing, invalid, rate-limited, or out of quota, workout tracking continues without AI coaching.

### gTTS

Requires network access to generate speech. If speech generation fails, the voice pipeline catches the failure and pauses coaching temporarily.

### WebRTC

Requires a browser with camera permission. Network or browser restrictions can prevent the video stream even when the Python application is running.

## 16. Current Limitations and Improvement Ideas

- Username login is not password-based authentication.
- Exercise thresholds are fixed constants and may need personalization.
- Detectors generally choose one visible side, which may be less reliable when the body is partially occluded.
- Repetition accuracy depends on camera angle, lighting, visibility, and full-body framing.
- gTTS is an online service and adds latency.
- Gemini free-tier quotas can be exhausted quickly during workouts.
- The application currently uses a single SQLite file, which is suitable for local use but not large multi-user deployment.
- Automated unit tests for detector landmarks and persistence flows should be added.

## 17. Recommended Testing Strategy

1. Test `BaseExercise.calculate_angle()` with known geometric points.
2. Test each detector with synthetic landmark fixtures representing up, down, and invalid-visibility states.
3. Test that one down-up cycle increments exactly one repetition.
4. Test `sync_metrics_update()` with fake processor contexts.
5. Test SQLite user creation and same-day exercise aggregation.
6. Test `VoicePipeline` with fake LLM and TTS clients.
7. Test quota errors and confirm tracking continues.
8. Run a browser smoke test with camera permission enabled.

## 18. Summary

This project combines five layers:

1. Streamlit UI for planning and displaying workouts.
2. WebRTC and MediaPipe for camera-based pose detection.
3. Exercise detectors for angles, form statuses, and repetitions.
4. SQLite for users and workout history.
5. Gemini plus gTTS for optional AI voice coaching.

The key data path is:

```text
camera frame -> pose landmarks -> exercise detector -> latest metrics
-> Streamlit session state -> set persistence and optional coaching
```

The project continues to provide exercise tracking even when the optional Gemini coaching service is unavailable.
