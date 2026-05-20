import os

file_path = "/Volumes/HDD MacOSv2/03 UK Agency/11 LevelOne Agency UK/02 Projects/07-voice-agent-v2/app/dashboard/index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

emoji_map = {
    "📊": "layout-dashboard",
    "📡": "radio",
    "📋": "list",
    "🧠": "brain",
    "🔌": "plug",
    "🤖": "bot",
    "📅": "calendar",
    "🏷️": "tag",
    "✉️": "mail",
    "👥": "users",
    "💡": "lightbulb",
    "⚙️": "settings",
    "🔑": "key",
    "🗑️": "trash-2",
    "⚡": "zap"
}

for emoji, icon_name in emoji_map.items():
    content = content.replace(emoji, f'<i data-lucide="{icon_name}" style="width: 1.2em; height: 1.2em; vertical-align: middle;"></i>')

if "lucide@latest" not in content:
    content = content.replace("</head>", "  <script src=\"https://unpkg.com/lucide@latest\"></script>\n</head>")

if "lucide.createIcons()" not in content:
    content = content.replace("initDashboard();", "initDashboard();\n    lucide.createIcons();")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Icons replaced.")
