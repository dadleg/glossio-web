# Glossio Web - Features & Changelog

## Core Features

### 1. Translation Editor
- **Segmented Editing**: Translate documents segment by segment.
- **Rich Context**: View paragraph context, source text, and notes.
- **Resources Integration**:
    - **Translation Memory (TM)**: Auto-suggestions from previous translations.
    - **Glossary**: Highlighted terms with definitions.
    - **Bible & EGW**: Auto-linking and fetching of Bible verses and EGW writings.
- **Keyboard Shortcuts**: Efficient navigation (Ctrl+Enter to save/next, Ctrl+Up/Down to move).

### 2. Real-time Collaboration
- **Live Sync**: See collaborators' changes in real-time as they type.
- **Segment Locking**: Prevents conflicting edits by locking a segment when a user selects it.
- **Presence Indicators**: See who is online and which segment they are working on.
- **Click-to-Jump**: Click a user's badge to scroll to their current position.

### 3. Project Management
- **DOCX Support**: Upload and translate Word documents.
- **Export**: Download the translated document with original formatting preserved.
- **User Assignment**: Assign specific users to projects.

### 4. User Management
- **Roles**: Admin and Standard User roles.
- **Authentication**: Secure login system.

---

## Changelog

### [Unreleased] - 2025-12-04
#### Added
- **Real-time Collaboration**:
    - Implemented WebSocket-based synchronization for immediate updates.
    - Added "Google Docs" style typing indicators and live text updates.
- **Segment Locking**:
    - Segments now lock automatically when a user selects them.
    - Visual indicators (greyed out, lock badge) for locked segments.
    - "[Name] is working..." placeholder for locked segments.
- **User Presence**:
    - Added user badges in the header to show active collaborators.
    - Implemented inactivity timeout (5 mins) to remove away users.
- **UI Refinements**:
    - Improved "Last edited by" log visibility and formatting.
    - Fixed Bible verse input to accept only numbers and disable autocomplete.
    - Removed redundant "Settings saved" alerts.

#### Fixed
- Fixed a critical bug where segment saving failed due to a type mismatch in user ID comparison.
- Fixed a server crash caused by missing `datetime` import.
- Fixed database schema update script to correctly target PostgreSQL.

### [1.0.0] - 2025-12-03
#### Added
- Initial release of Glossio Web.
- Basic translation editor with TM and Glossary.
- Project creation and file parsing.
