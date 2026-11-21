# Known LoiLoNote DOM selectors (updated to match the live 7.13.x UI).
# These are best-effort and may need adjustment after inspecting live pages.

# Note list view
NOTE_LIST_CONTAINER = ".standardNoteList, [class*='standardNoteList'], [class*='noteList']"
NOTE_CARD = ".noteListListItemGrid, [class*='noteListListItemGrid']"
NOTE_TITLE = ".gridAreaNoteName, [class*='gridAreaNoteName']"
NOTE_DATE = ".gridAreaNoteUpdatedDate, [class*='gridAreaNoteUpdatedDate']"
NOTE_LINK = "a[href]"

# Course list view
COURSE_ITEM = ".courseListItem, [class*='courseListItem']"

# Tabs
TAB_STANDARD_NOTE = "#_r_5_-standardNoteList, [id*='standardNoteList']"
TAB_SUBMISSION = "#_r_5_-submissionBox, [id*='submissionBox']"
TAB_TIMELINE = "#_r_5_-timeline, [id*='timeline']"

# Editor / toolbar
EDITOR_LEFT_TOOLBAR = ".menuWrapper, [class*='menuWrapper']"
CLOSE_BUTTON = "button[class*='close'], .closeButton, [aria-label*='close'], [aria-label*='閉じる']"

# Popovers / menus
POPOVER = "[class*='popover'], [class*='menu'], [role='menu']"

# Course / class panels
COURSE_PANEL = "[class*='course'], [class*='classPanel'], [class*='lesson']"

# Tabs (icon-matching text colors; do not force white)
TAB = "[class*='tab'], [role='tab']"

# Materials box (資料箱)
MATERIALS_CONTAINER = ".materialBox, [class*='materialBox']"
MATERIAL_FOLDER = ".materialBoxDialogDocumentCell, [class*='materialBoxDialogDocumentCell']"
MATERIAL_ITEM = ".materialBoxDialogDocumentCell, [class*='materialBoxDialogDocumentCell']"
MATERIAL_DOWNLOAD = "a[download], button[class*='download'], [class*='download']"

# Submission box (提出箱)
SUBMISSION_CONTAINER = "[class*='submission'], [class*='submit']"
SUBMISSION_UPLOAD = "input[type='file'], button[class*='upload']"

# Send to individual
SEND_RECIPIENT = "[class*='recipient'], [class*='student'], select, [class*='user']"
SEND_BUTTON = "button[class*='send'], [class*='send']"

# Create note
CREATE_NOTE_BUTTON = "button[class*='create'], button[class*='new'], [class*='addNote'], [aria-label*='作成'], [aria-label*='新規'], [aria-label*='create'], [aria-label*='add']"
NOTE_TITLE_INPUT = "input[class*='title'], input[placeholder*='タイトル'], input[placeholder*='title']"
