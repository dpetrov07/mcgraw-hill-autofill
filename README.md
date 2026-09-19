# McGraw Hill Autofill

McGraw Hill Autofill is a macOS homework autofill utility for McGraw Hill Connect. It
uses Hammerspoon, browser automation, and the OpenAI API to read a visible Connect
question in Google Chrome or Safari, generate an answer, and autofill supported
answer controls with **Option+Q**. Useful search terms: McGraw Hill Connect
autofill, Connect homework helper, homework answer automation, fill in the blank
autofill, multiple-choice autofill, and Hammerspoon homework automation.

- It works with text-only questions whose visible answer controls are standard text
  fields (including multiple blanks), number fields, radio-button multiple choice,
  or checkbox multiple-select.
- It does not support dropdowns, editable tables, matching/drag-and-drop controls,
  or questions that depend on images, graphs, diagrams, canvases, or other visual context.
- The utility never clicks **Submit**.
- Only the question extracted from the browser DOM is sent to OpenAI.
- Successful runs are silent. The page control changes, but no answer popup appears.

## Requirements

- A Mac. Hammerspoon and the browser automation used here are macOS-only.
- Google Chrome or Safari.
- Python 3.10 or newer. Check with `python3 --version`. If the command is missing,
  install Python from [python.org](https://www.python.org/downloads/macos/).
- Git. Check with `git --version`. If macOS asks to install the Command Line Tools,
  accept the prompt and run the command again after installation finishes.
- An OpenAI API account with API billing or credits enabled. A ChatGPT subscription
  does not include API usage.

## Complete setup

### 1. Clone the repository

On the repository's GitHub page, click **Code**, copy the HTTPS URL, then open
Terminal and run the following. Replace the example URL with the URL you copied.

```zsh
git clone https://github.com/YOUR-ACCOUNT/mcgraw-hill-autofill.git
cd mcgraw-hill-autofill
```

Keep the repository in a permanent location. Moving it later will require updating
the paths in the Hammerspoon configuration.

### 2. Create the Python environment

From inside the cloned repository, run:

```zsh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install openai python-dotenv
```

The first command creates an isolated Python environment in `.venv`. The final
command installs the only two third-party Python packages used by the script.

### 3. Add an OpenAI API key

1. Create a secret key on the
   [OpenAI API keys page](https://platform.openai.com/api-keys).
2. In Terminal, while still inside the repository, run:

   ```zsh
   touch .env
   open -e .env
   ```

3. Add this line, replacing the placeholder with the key you created:

   ```ini
   OPENAI_API_KEY=your_key_here
   ```

4. Save and close the file.

Do not commit or share `.env`. It is already listed in this repository's
`.gitignore`.

### 4. Install Hammerspoon

1. Download the latest release from [hammerspoon.org](https://www.hammerspoon.org/).
2. Open the download and drag **Hammerspoon.app** into `/Applications`.
3. Open Hammerspoon from the Applications folder.
4. Follow its prompt to grant Accessibility access. If there is no prompt, open
   **System Settings > Privacy & Security > Accessibility** and turn on
   **Hammerspoon**.

Hammerspoon runs from the hammer icon in the macOS menu bar. It does nothing until
an `init.lua` configuration is loaded.

### 5. Point the Hammerspoon script at this clone

First, print the repository's full path:

```zsh
pwd
```

Copy the output. Open the included Hammerspoon script:

```zsh
open -e init.lua
```

Near the top of the file, replace the existing `python` and `script` values with
paths based on the output of `pwd`. For example, if `pwd` printed
`/Users/alex/Projects/mcgraw-hill-autofill`, use:

```lua
local python = "/Users/alex/Projects/mcgraw-hill-autofill/.venv/bin/python"
local script = "/Users/alex/Projects/mcgraw-hill-autofill/homework_review.py"
```

Save the file. Both paths must be absolute; `~` will not be expanded here.

Next, create or open Hammerspoon's main configuration:

```zsh
mkdir -p ~/.hammerspoon
touch ~/.hammerspoon/init.lua
open -e ~/.hammerspoon/init.lua
```

Add the following line, again using the actual path printed by `pwd`:

```lua
dofile("/Users/alex/Projects/mcgraw-hill-autofill/init.lua")
```

If `~/.hammerspoon/init.lua` already contains other automations, add this line at
the end instead of replacing the existing content. Save the file, click the
Hammerspoon menu-bar icon, and choose **Reload Config**. If a Lua error appears,
recheck the three absolute paths above.

### 6. Grant macOS permissions

Open **System Settings > Privacy & Security** and confirm the following permissions.
macOS may require you to authenticate, quit an app, or reopen it after a change.

| Privacy setting | What to enable | Why it is needed |
| --- | --- | --- |
| Accessibility | Hammerspoon | Registers the keyboard shortcut. |
| Automation | Allow Hammerspoon to control Google Chrome and/or Safari | Reads the current page and enters supported answers through Apple Events. |

The browser entries under **Automation** may not appear until the first time you
press **Option+Q**. When macOS says Hammerspoon wants to control the browser, click
**Allow**, then return to System Settings and confirm that its browser toggle is on.
If macOS lists Python instead of Hammerspoon for one of these permissions, enable
the listed Python process as well.

After changing Accessibility, quit Hammerspoon completely and open it again.

### 7. Configure a browser

Only configure the browser you plan to use. The browser must allow JavaScript sent
through Apple Events; ordinary website JavaScript being enabled is not enough.

#### Google Chrome

1. Open Chrome.
2. In the macOS menu bar, choose **View > Developer > Allow JavaScript from Apple
   Events**.
3. Accept the confirmation prompt.
4. Open the menu again and confirm that the item has a checkmark.

This is a Chrome application-menu setting, not a setting on the `chrome://settings`
page. If **Developer** is not visible, make sure Chrome is the active application
and that you are using the macOS menu bar at the top of the screen.

#### Safari

1. Open **Safari > Settings > Security** and make sure **Enable JavaScript** is on.
2. Open **Safari > Settings > Advanced** and enable **Show features for web
   developers**.
3. Open the new **Develop** menu in the macOS menu bar.
4. On recent Safari versions, choose **Develop > Developer Settings**, open the
   **Automation** section, and enable **Allow JavaScript from Apple Events**. On
   older versions, choose **Develop > Allow JavaScript from Apple Events** directly.
5. Accept the confirmation prompt and confirm the setting remains enabled.

### 8. Verify the installation

1. Open Chrome or Safari and sign in to McGraw Hill Connect.
2. Navigate to a question and leave the entire question and its answer controls
   visible. Keep that browser as the frontmost application.
3. Press **Option+Q**.
4. Approve any first-run Automation prompt from macOS.
5. Wait for the supported field or choice to be filled in. There is no success
   popup. Review the result yourself before submitting.

## Shortcuts

| Shortcut | Action |
| --- | --- |
| **Option+Q** | Read the current question and fill a supported answer control. |

## Troubleshooting

### Nothing happens when I press the shortcut

- Confirm Hammerspoon is running and its hammer icon is in the menu bar.
- Choose **Reload Config** from the Hammerspoon menu.
- Choose **Console** from that menu and look for a path or Lua error.
- Recheck **System Settings > Privacy & Security > Accessibility**.
- Check that another application has not already claimed the same shortcut.

### “Worker could not start” or “worker stopped”

Recheck the two paths at the top of the repository's `init.lua`. Confirm the
virtual environment and imports with:

```zsh
.venv/bin/python -c 'import openai, dotenv; print("Python setup is OK")'
```

If that fails, repeat step 2.

### Browser access fails

- Confirm the browser is frontmost and a Connect question is visible.
- Recheck **Allow JavaScript from Apple Events** in that browser.
- Recheck **System Settings > Privacy & Security > Automation**.
- Quit and reopen both Hammerspoon and the browser after changing permissions.
- Connect page updates may change its HTML and require a code update.

### OpenAI authentication or billing error

- Open `.env` and confirm the key is on one line with no extra spaces.
- Confirm the API key is active and the API account has billing or credits enabled.
- Reload the Hammerspoon config after changing `.env`; this restarts the worker.

### An error says the question is not supported

Automatic entry supports fill-in-the-blank, numeric, multiple-choice, and
multiple-select questions. Dropdowns, editable tables, unknown layouts, and
questions that depend on images, graphs, canvases, or other visual context are not
sent to OpenAI because their answers cannot be auto-filled reliably.

## Debug and manual runs

To inspect DOM extraction without making an OpenAI request, put the question on
screen and run this from the repository:

```zsh
.venv/bin/python homework_review.py "Google Chrome" --debug
```

Use `"Safari"` instead when Safari is showing the question.

For Hammerspoon debugging, change `homeworkReviewDebug` near the top of the
repository's `init.lua` to `true`, save it, and choose **Reload Config**. Press
**Option+Q**, then open the Hammerspoon Console. It prints the normalized payload,
structured answer values, and request timings without applying the answer. Set the value
back to `false` and reload when finished.

To perform a complete manual run without the keyboard shortcut:

```zsh
.venv/bin/python homework_review.py "Google Chrome"
```

The browser must already be open, frontmost, and displaying the question. A
successful run prints nothing; the answer is visible in the page control.
