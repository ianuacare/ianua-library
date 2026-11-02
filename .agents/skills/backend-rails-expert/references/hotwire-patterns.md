# Hotwire Patterns — Reference

This file is loaded on demand when the task involves Turbo Frames, Turbo Streams, or Stimulus controllers.

---

## Stack

| Tool | Purpose |
|---|---|
| Turbo Drive | SPA-like navigation without JS (enabled by default) |
| Turbo Frames | Partial page updates via frame decomposition |
| Turbo Streams | Targeted DOM mutations (append, prepend, replace, remove, update) |
| Stimulus | Lightweight JS controllers for behavior |
| Importmap | JS dependency management (no bundler) |

---

## Turbo Frames

### Basic Frame

```slim
/ app/views/backoffice/pathways/show.html.slim
= turbo_frame_tag @pathway do
  h1 = @pathway.name
  p = @pathway.description
  = link_to t(".edit"), edit_backoffice_pathway_path(@pathway)
```

### Lazy-Loading Frame

```slim
/ Load content on demand
= turbo_frame_tag "pathway_stats", src: backoffice_pathway_stats_path(@pathway), loading: :lazy do
  / Placeholder shown while loading
  p = t(".loading")
```

### Frame Navigation

```slim
/ Link targets the frame it's inside (default)
= turbo_frame_tag "pathways_list" do
  - @pathways.each do |pathway|
    = link_to pathway.name, backoffice_pathway_path(pathway)

/ Link breaks out of the frame
= link_to "Home", root_path, data: { turbo_frame: "_top" }
```

**Rules:**
- Frames scope navigation — links inside a frame update only that frame
- Use `data: { turbo_frame: "_top" }` to break out of a frame
- Use `loading: :lazy` for content below the fold
- Controller responds normally — Turbo extracts the matching frame from the response

---

## Turbo Streams

### From Controller

```ruby
# app/controllers/backoffice/pathways_controller.rb
def create
  @pathway = Pathway.new(pathway_params)
  authorize! @pathway

  if @pathway.save
    respond_to do |format|
      format.html { redirect_to backoffice_pathway_path(@pathway), status: :see_other }
      format.turbo_stream
    end
  else
    render :new, status: :unprocessable_entity
  end
end
```

```slim
/ app/views/backoffice/pathways/create.turbo_stream.slim
= turbo_stream.prepend "pathways_list" do
  = render partial: "backoffice/pathways/pathway", locals: { pathway: @pathway }

= turbo_stream.update "pathways_count" do
  = Pathway.count
```

### Stream Actions

| Action | Effect |
|---|---|
| `append` | Add to end of target |
| `prepend` | Add to start of target |
| `replace` | Replace entire target element |
| `update` | Replace target's innerHTML |
| `remove` | Remove target element |
| `before` | Insert before target |
| `after` | Insert after target |

### From Model (Broadcast)

```ruby
class Message < ApplicationRecord
  after_create_commit -> { broadcast_append_to "messages" }
  after_update_commit -> { broadcast_replace_to "messages" }
  after_destroy_commit -> { broadcast_remove_to "messages" }
end
```

**Rules:**
- Use Turbo Streams for targeted updates without full page reload
- Always provide an HTML fallback via `format.html` in `respond_to`
- Stream templates use `.turbo_stream.slim` extension
- Broadcasts require Solid Cable (ActionCable) for WebSocket delivery

---

## Stimulus Controllers

### File Location

```
app/javascript/controllers/
├── application.js          # Base setup
├── index.js                # Auto-registration
├── hello_controller.js     # Example
├── modal_controller.js     # Modal behavior
└── search_controller.js    # Search behavior
```

### Basic Controller

```javascript
// app/javascript/controllers/clipboard_controller.js
import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["source"]
  static values = { successMessage: { type: String, default: "Copied!" } }

  copy() {
    navigator.clipboard.writeText(this.sourceTarget.value)
  }
}
```

### Connecting in Slim

```slim
div[data-controller="clipboard"]
  input[data-clipboard-target="source" value=@pathway.share_url]
  button[data-action="click->clipboard#copy"] = t(".copy")
```

### Stimulus Conventions

| Attribute | Purpose | Example |
|---|---|---|
| `data-controller` | Connect controller | `data-controller="modal"` |
| `data-action` | Bind event to method | `data-action="click->modal#open"` |
| `data-{name}-target` | Reference element | `data-modal-target="dialog"` |
| `data-{name}-{key}-value` | Pass data | `data-modal-open-value="true"` |

**Rules:**
- One controller per behavior (SRP)
- Use `static targets` for element references — never `querySelector` in Stimulus
- Use `static values` for configuration — typed, with defaults
- Connect/disconnect lifecycle: use `connect()` and `disconnect()` for setup/teardown
- Never manipulate DOM outside the controller's element scope
- No `console.log` — use `console.debug` during development, remove before commit

---

## Importmap

JavaScript dependencies are managed via Importmap (no webpack, no esbuild):

```ruby
# config/importmap.rb
pin "application"
pin "@hotwired/turbo-rails", to: "turbo.min.js"
pin "@hotwired/stimulus", to: "stimulus.min.js"
pin "@hotwired/stimulus-loading", to: "stimulus-loading.js"
pin_all_from "app/javascript/controllers", under: "controllers"
```

**Rules:**
- Add JS dependencies with `bin/importmap pin <package>`
- Audit with `bin/importmap audit`
- No `node_modules`, no `package.json`, no bundler
- Stimulus controllers are auto-registered via `pin_all_from`

---

## Redirects After Mutation

```ruby
redirect_to backoffice_pathways_path, status: :see_other, notice: t(".notice")
```

**Rules:**
- After POST/PATCH/DELETE, redirect with `status: :see_other` (303) for Turbo compatibility
- Turbo Drive follows 303 redirects with GET — prevents form resubmission
- For Turbo Stream responses, no redirect needed (stream updates the DOM in place)
- Failed form submissions render with `status: :unprocessable_entity` (422) for Turbo to replace the frame
