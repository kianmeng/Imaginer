# main.py
#
# Copyright 2023 Me
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import gi
import sys
import threading
import json

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gst", "1.0")
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk, Gio, Adw, Gdk, GLib, Gst, WebKit
from .window import BavarderWindow
from .preferences import Preferences
from enum import auto, IntEnum

from .constants import app_id, version

from tempfile import NamedTemporaryFile

from .provider import PROVIDERS
import platform
import os
import markdown
import tempfile
import re

class Step(IntEnum):
    CONVERT_HTML = auto()
    LOAD_WEBVIEW = auto()
    RENDER = auto()



class BavarderApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self):
        super().__init__(
            application_id="io.github.Bavarder.Bavarder",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.create_action("quit", self.on_quit, ["<primary>q"])
        self.create_action("about", self.on_about_action)
        self.create_action(
            "preferences", self.on_preferences_action, ["<primary>comma"]
        )
        self.create_action("copy_prompt", self.on_copy_prompt_action)
        self.create_action("copy_bot", self.on_copy_bot_action, ["<primary><shift>c"])
        self.create_action("ask", self.on_ask_action, ["<primary>Return"])
        self.create_action("clear", self.on_clear_action, ["<primary><shift>BackSpace"])
        # self.create_action("speak", self.on_speak_action, ["<primary>S"])
        # self.create_action("listen", self.on_listen_action, ["<primary>L"])

        self.settings = Gio.Settings(schema_id="io.github.Bavarder.Bavarder")

        self.clear_after_send = self.settings.get_boolean("clear-after-send")

        self.enabled_providers = sorted(
            set(self.settings.get_strv("enabled-providers"))
        )
        self.latest_provider = self.settings.get_string("latest-provider")

        self.web_view = None
        self.web_view_pending_html = None

        self.loading = False
        self.shown = False
        self.preview_visible = False



    def quitting(self, *args, **kwargs):
        """Called before closing main window."""
        self.settings.set_strv("enabled-providers", list(self.enabled_providers))
        self.settings.set_string("latest-provider", self.get_provider().slug)

        print("Saving providers data...")

        self.save_providers()
        self.quit()

    def on_quit(self, action, param):
        """Called when the user activates the Quit action."""
        self.quitting()

    def save_providers(self):
        r = {}
        for k, p in self.providers.items():
            r[p.slug] = json.dumps(p.save())
        print(r)
        data = GLib.Variant("a{ss}", r)
        self.settings.set_value("providers-data", data)

    def on_clear_action(self, action, param):
        self.win.bot_text_view.get_buffer().set_text("")
        self.win.prompt_text_view.get_buffer().set_text("")
        self.win.prompt_text_view.grab_focus()

    def get_provider(self):
        print(self.providers)
        return self.providers[self.win.provider_selector.props.selected]

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        self.win = self.props.active_window
        if not self.win:
            self.win = BavarderWindow(application=self)
        self.win.present()

        self.win.connect("close-request", self.quitting)

        self.load_dropdown()

        self.load()

        print(self.latest_provider)
        for k, p in self.providers.items():
            if p.slug == self.latest_provider:
                print("Setting selected provider to", k)
                self.win.provider_selector.set_selected(k)
                break

        self.win.prompt_text_view.grab_focus()

    def load_dropdown(self):

        self.provider_selector_model = Gtk.StringList()
        self.providers = {}

        self.providers_data = self.settings.get_value("providers-data")
        print(self.providers_data)
        print(self.enabled_providers)

        for provider, i in zip(
            self.enabled_providers, range(len(self.enabled_providers))
        ):
            print("Loading provider", provider)
            try:
                self.provider_selector_model.append(PROVIDERS[provider].name)
            except KeyError:
                print("Provider", provider, "not found")
                self.enabled_providers.remove(provider)
                continue
            else:
                try:
                    _ = self.providers[i]  # doesn't re load if already loaded
                except KeyError:
                    self.providers[i] = PROVIDERS[provider](self.win, self)

        self.win.provider_selector.set_model(self.provider_selector_model)
        self.win.provider_selector.connect("notify", self.on_provider_selector_notify)

    def load(self):
        for p in self.providers.values():
            print(self.providers_data)
            try:
                p.load(data=json.loads(self.providers_data[p.slug]))
            except KeyError:  # provider not in data
                pass

    def on_provider_selector_notify(self, _unused, pspec):
        self.win.banner.set_revealed(False)

    def on_about_action(self, widget, _):
        """Callback for the app.about action."""
        about = Adw.AboutWindow(
            transient_for=self.props.active_window,
            application_name="Bavarder",
            application_icon=app_id,
            developer_name="0xMRTT",
            developers=["0xMRTT https://github.com/0xMRTT"],
            designers=["David Lapshin https://github.com/daudix-UFO"],
            artists=["David Lapshin https://github.com/daudix-UFO"],
            documenters=[],
            translator_credits="""0xMRTT <0xmrtt@proton.me>
                David Lapshin <ddaudix@gmail.com>
                Morgan Antonsson <morgan.antonsson@gmail.com>
                thepoladov13 <thepoladov@protonmail.com>
                Muznyo <codeberg.vqtek@simplelogin.com>
                Deimidis <gmovia@pm.me>
                sjdonado <jsrd98@gmail.com>
                artnay <jiri.gronroos@iki.fi>
                Rene Coty <irenee.thirion@e.email>
                galegovski <galegovski@outlook.com>""",
            license_type=Gtk.License.GPL_3_0,
            version=version,
            website="https://bavarder.codeberg.page",
            issue_url="https://github.com/Bavarder/Bavarder/issues",
            support_url="https://codeberg.org/Bavarder/Bavarder/issues",
            copyright="© 2023 0xMRTT",
        )

        about.add_acknowledgement_section(
            "Special thanks to",
            [
                "Telegraph https://apps.gnome.org/app/io.github.fkinoshita.Telegraph",
            ],
        )
        about.set_debug_info(
            f"""{app_id} {version}
Environment: {os.environ.get("XDG_CURRENT_DESKTOP", "Unknown")}
Gtk: {Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}.{Gtk.MICRO_VERSION}
Python: {platform.python_version()}
OS: {platform.system()} {platform.release()} {platform.version()}
Providers: {self.enabled_providers}
"""
        )
        about.present()

    def on_preferences_action(self, widget, *args, **kwargs):
        """Callback for the app.preferences action."""
        preferences = Preferences(
            application=self, transient_for=self.props.active_window
        )
        preferences.present()

    def on_copy_prompt_action(self, widget, _):
        """Callback for the app.copy_prompt action."""

        toast = Adw.Toast()

        text = self.win.prompt_text_view.get_buffer()
        toast.set_title("Text copied")

        (start, end) = text.get_bounds()
        text = text.get_text(start, end, False)

        if len(text) == 0:
            return

        Gdk.Display.get_default().get_clipboard().set(text)

        self.win.toast_overlay.add_toast(toast)

    def on_copy_bot_action(self, widget, _):
        """Callback for the app.copy_bot action."""

        toast = Adw.Toast()

        text = self.win.bot_text_view.get_buffer()
        toast.set_title("Text copied")

        (start, end) = text.get_bounds()
        text = text.get_text(start, end, False)

        if len(text) == 0:
            return

        Gdk.Display.get_default().get_clipboard().set(text)

        self.win.toast_overlay.add_toast(toast)

    def ask(self, prompt):
        return self.providers[self.provider].ask(prompt)

    @staticmethod
    def on_click_link(web_view, decision, _decision_type):
        if web_view.get_uri().startswith(("http://", "https://", "www.")):
            Glib.spawn_command_line_async(f"xdg-open {web_view.get_uri()}")
            decision.ignore()
            return True

    @staticmethod
    def on_right_click(web_view, context_menu, _event, _hit_test):
        # disable some context menu option
        for item in context_menu.get_items():
            if item.get_stock_action() in [WebKit.ContextMenuAction.RELOAD,
                                           WebKit.ContextMenuAction.GO_BACK,
                                           WebKit.ContextMenuAction.GO_FORWARD,
                                           WebKit.ContextMenuAction.STOP]:
                context_menu.remove(item)


    def show(self, html=None, step=Step.LOAD_WEBVIEW):
        if step == Step.LOAD_WEBVIEW:
            self.loading = True
            if not self.web_view:
                self.web_view = WebKit.WebView()
                self.web_view.get_settings().set_allow_universal_access_from_file_urls(True)
                #TODO: enable devtools on Devel profile
                self.web_view.get_settings().set_enable_developer_extras(True)

                # Show preview once the load is finished
                self.web_view.connect("load-changed", self.on_load_changed)

                # All links will be opened in default browser, but local files are opened in apps.
                self.web_view.connect("decide-policy", self.on_click_link)

                self.web_view.connect("context-menu", self.on_right_click)

                self.web_view.set_hexpand(True)
                self.web_view.set_vexpand(True)

                self.win.response_stack.add_child(self.web_view)
                self.win.response_stack.set_visible_child(self.web_view)
            

            print(html)
            if self.web_view.is_loading():
                self.web_view_pending_html = html
            else:
                self.web_view.load_html(html, "file://localhost/")


        elif step == Step.RENDER:
            if not self.preview_visible:
                self.preview_visible = True
                self.show()

    def reload(self, *_widget, reshow=False):
        if self.preview_visible:
            if reshow:
                self.hide()
            self.show()

    def on_load_changed(self, _web_view, event):
        if event == WebKit.LoadEvent.FINISHED:
            self.loading = False
            if self.web_view_pending_html:
                self.show(html=self.web_view_pending_html, step=Step.LOAD_WEBVIEW)
                self.web_view_pending_html = None
            else:
                # we only lazyload the webview once
                self.show(step=Step.RENDER)

    def parse_css(self, path):

        adw_palette_prefixes = [
            "blue_",
            "green_",
            "yellow_",
            "orange_",
            "red_",
            "purple_",
            "brown_",
            "light_",
            "dark_"
        ]

        # Regular expressions
        not_define_color = re.compile(r"(^(?:(?!@define-color).)*$)")
        define_color = re.compile(r"(@define-color .*[^\s])")
        css = ""
        variables = {}
        palette = {}

        for color in adw_palette_prefixes:
            palette[color] = {}

        with open(path, "r", encoding="utf-8") as sheet:
            for line in sheet:
                cdefine_match = re.search(define_color, line)
                not_cdefine_match = re.search(not_define_color, line)
                if cdefine_match != None: # If @define-color variable declarations were found
                    palette_part = cdefine_match.__getitem__(1) # Get the second item of the re.Match object
                    name, color = palette_part.split(" ", 1)[1].split(" ", 1)
                    if name.startswith(tuple(adw_palette_prefixes)): # Palette colors
                        palette[name[:-1]][name[-1:]] = color[:-1]
                    else: # Other color variables
                        variables[name] = color[:-1]
                elif not_cdefine_match != None: # If CSS rules were found
                    css_part = not_cdefine_match.__getitem__(1)
                    css += f"{css_part}\n"

            sheet.close()
            return variables, palette, css
            
    def update_response(self, response):
        """Update the response text view with the response."""
        response = markdown.markdown(response, extensions=["markdown.extensions.extra"])

        TEMPLATE = """
        <html>
            <head>
                <style>
                    @font-face {
                    font-family: fira-sans;
                    src: url("/app/share/fonts/FiraSans-Regular.ttf") format("ttf"),
                        local("FiraSans-Regular"),
                        url("https://fonts.gstatic.com/s/firasans/v10/va9E4kDNxMZdWfMOD5Vvl4jL.woff2") format("woff2");
                    }

                    @font-face {
                    font-family: fira-mono;
                    src: url("/app/share/fonts/FiraMono-Regular.ttf") format("ttf"),
                        local("FiraMono-Regular"),
                        url("https://fonts.gstatic.com/s/firamono/v9/N0bX2SlFPv1weGeLZDtgJv7S.woff2") format("woff2");
                    }

                    @font-face {
                    font-family: color-emoji;
                    src: local("Noto Color Emoji"), local("Apple Color Emoji"), local("Segoe UI Emoji"), local("Segoe UI Symbol");
                    }

                    {theme_css}

                    * {
                    box-sizing: border-box;
                    }

                    html {
                    font-size: 16px;
                    }

                    body {
                    color: var(--text-color);
                    background-color: var(--background-color);
                    font-family: "Fira Sans", fira-sans, sans-serif, color-emoji;
                    line-height: 1.5;
                    word-wrap: break-word;
                    max-width: 980px;
                    margin: auto;
                    padding: 4em;
                    }

                    @media screen and (max-width: 799px) {
                    html {
                        font-size: 14px;
                    }

                    body {
                        padding: 1em;
                    }
                    }

                    @media screen and (min-width: 1280px) {
                    html {
                        font-size: 18px;
                    }
                    }

                    a {
                    background-color: transparent;
                    color: var(--link-color);
                    text-decoration: none;
                    }

                    a:active,
                    a:hover {
                    outline-width: 0;
                    }

                    a:hover {
                    text-decoration: underline;
                    }

                    strong {
                    font-weight: 600;
                    }

                    img {
                    border-style: none;
                    }

                    hr {
                    box-sizing: content-box;
                    height: 0.25em;
                    padding: 0;
                    margin: 1.5em 0;
                    overflow: hidden;
                    background-color: var(--hr-background-color);
                    border: 0;
                    }

                    hr::before {
                    display: table;
                    content: "";
                    }

                    hr::after {
                    display: table;
                    clear: both;
                    content: "";
                    }

                    input {
                    font-family: inherit;
                    font-size: inherit;
                    line-height: inherit;
                    margin: 0;
                    overflow: visible;
                    }

                    [type="checkbox"] {
                    box-sizing: border-box;
                    padding: 0;
                    }

                    table {
                    border-spacing: 0;
                    border-collapse: collapse;
                    }

                    td,
                    th {
                    padding: 0;
                    }

                    h1,
                    h2,
                    h3,
                    h4,
                    h5,
                    h6 {
                    font-weight: 600;
                    margin: 0;
                    }

                    h1 {
                    font-size: 2em;
                    }

                    h2 {
                    font-size: 1.5em;
                    }

                    h3 {
                    font-size: 1.25em;
                    }

                    h4 {
                    font-size: 1em;
                    }

                    h5 {
                    font-size: 0.875em;
                    }

                    h6 {
                    font-size: 0.85em;
                    }

                    p {
                    margin-top: 0;
                    margin-bottom: 0.625em;
                    }

                    blockquote {
                    margin: 0;
                    }

                    ul,
                    ol {
                    padding-left: 0;
                    margin-top: 0;
                    margin-bottom: 0;
                    }

                    ol ol,
                    ul ol {
                    list-style-type: lower-roman;
                    }

                    ul ul ol,
                    ul ol ol,
                    ol ul ol,
                    ol ol ol {
                    list-style-type: lower-alpha;
                    }

                    dd {
                    margin-left: 0;
                    }

                    code,
                    kbd,
                    pre {
                    font-family: "Fira Mono", fira-mono, monospace, color-emoji;
                    font-size: 1em;
                    word-wrap: normal;
                    }

                    code {
                    border-radius: 0.1875em;
                    font-size: 0.85em;
                    padding: 0.2em 0.4em;
                    margin: 0;
                    }

                    pre {
                    margin-top: 0;
                    margin-bottom: 0;
                    font-size: 0.75em;
                    }

                    pre>code {
                    padding: 0;
                    margin: 0;
                    font-size: 1em;
                    word-break: normal;
                    white-space: pre;
                    background: transparent;
                    border: 0;
                    }

                    .highlight {
                    margin-bottom: 1em;
                    }

                    .highlight pre {
                    margin-bottom: 0;
                    word-break: normal;
                    }

                    .highlight pre,
                    pre {
                    padding: 1em;
                    overflow: auto;
                    font-size: 0.85em;
                    line-height: 1.5;
                    background-color: var(--alt-background-color);
                    border-radius: 0.1875em;
                    }

                    pre code {
                    background-color: transparent;
                    border: 0;
                    display: inline;
                    padding: 0;
                    margin: 0;
                    overflow: visible;
                    line-height: inherit;
                    word-wrap: normal;
                    }

                    .pl-0 {
                    padding-left: 0 !important;
                    }

                    .pl-1 {
                    padding-left: 0.25em !important;
                    }

                    .pl-2 {
                    padding-left: 0.5em !important;
                    }

                    .pl-3 {
                    padding-left: 1em !important;
                    }

                    .pl-4 {
                    padding-left: 1.5em !important;
                    }

                    .pl-5 {
                    padding-left: 2em !important;
                    }

                    .pl-6 {
                    padding-left: 2.5em !important;
                    }

                    .markdown-body::before {
                    display: table;
                    content: "";
                    }

                    .markdown-body::after {
                    display: table;
                    clear: both;
                    content: "";
                    }

                    .markdown-body>*:first-child {
                    margin-top: 0 !important;
                    }

                    .markdown-body>*:last-child {
                    margin-bottom: 0 !important;
                    }

                    a:not([href]) {
                    color: inherit;
                    text-decoration: none;
                    }

                    .anchor {
                    float: left;
                    padding-right: 0.25em;
                    margin-left: -1.25em;
                    line-height: 1;
                    }

                    .anchor:focus {
                    outline: none;
                    }

                    p,
                    blockquote,
                    ul,
                    ol,
                    dl,
                    table,
                    pre {
                    margin-top: 0;
                    margin-bottom: 1em;
                    }

                    blockquote {
                    padding: 0 1em;
                    color: var(--blockquote-text-color);
                    border-left: 0.25em solid var(--blockquote-border-color);
                    }

                    blockquote>:first-child {
                    margin-top: 0;
                    }

                    blockquote>:last-child {
                    margin-bottom: 0;
                    }

                    kbd {
                    display: inline-block;
                    padding: 0.1875em 0.3125em;
                    font-size: 0.6875em;
                    line-height: 1;
                    color: var(--kbd-text-color);
                    vertical-align: middle;
                    background-color: var(--kbd-background-color);
                    border: solid 1px var(--kbd-border-color);
                    border-bottom-color: var(--kbd-shadow-color);
                    border-radius: 3px;
                    box-shadow: inset 0 -1px 0 var(--kbd-shadow-color);;
                    }

                    h1,
                    h2,
                    h3,
                    h4,
                    h5,
                    h6 {
                    margin-top: 1.5em;
                    margin-bottom: 1em;
                    font-weight: 600;
                    line-height: 1.25;
                    }

                    h1:hover .anchor,
                    h2:hover .anchor,
                    h3:hover .anchor,
                    h4:hover .anchor,
                    h5:hover .anchor,
                    h6:hover .anchor {
                    text-decoration: none;
                    }

                    h1 {
                    padding-bottom: 0.3em;
                    font-size: 2em;
                    border-bottom: 1px solid var(--header-border-color);
                    }

                    h2 {
                    padding-bottom: 0.3em;
                    font-size: 1.5em;
                    border-bottom: 1px solid var(--header-border-color);
                    }

                    h3 {
                    font-size: 1.25em;
                    }

                    h4 {
                    font-size: 1em;
                    }

                    h5 {
                    font-size: 0.875em;
                    }

                    h6 {
                    font-size: 0.85em;
                    opacity: 0.67;
                    }

                    ul,
                    ol {
                    padding-left: 2em;
                    }

                    ul ul,
                    ul ol,
                    ol ol,
                    ol ul {
                    margin-top: 0;
                    margin-bottom: 0;
                    }

                    li {
                    overflow-wrap: break-word;
                    }

                    li>p {
                    margin-top: 1em;
                    }

                    li+li {
                    margin-top: 0.25em;
                    }

                    dl {
                    padding: 0;
                    }

                    dl dt {
                    padding: 0;
                    margin-top: 1em;
                    font-size: 1em;
                    font-style: italic;
                    font-weight: 600;
                    }

                    dl dd {
                    padding: 0 1em;
                    margin-bottom: 1em;
                    }

                    table {
                    display: block;
                    width: 100%;
                    overflow: auto;
                    }

                    table th {
                    font-weight: 600;
                    }

                    table th,
                    table td {
                    padding: 0.375em 0.8125em;
                    border: 1px solid var(--table-td-border-color);
                    }

                    table tr {
                    background-color: var(--background-color);
                    border-top: 1px solid var(--table-tr-border-color);
                    }

                    table tr:nth-child(2n) {
                    background-color: var(--alt-background-color);
                    }

                    img {
                    max-width: 100%;
                    box-sizing: content-box;
                    }

                    img[align=right] {
                    padding-left: 1.25em;
                    }

                    img[align=left] {
                    padding-right: 1.25em;
                    }

                    .task-list-item {
                    list-style-type: none;
                    }

                    .task-list-item+.task-list-item {
                    margin-top: 0.1875em;
                    }

                    .task-list-item input {
                    margin: 0 0.2em 0.25em -1.6em;
                    vertical-align: middle;
                    }
                </style>
            </head>
            <body>
                {response}
            </body>
        </html>
        """

        ADWAITA_STYLE = """:root {
                        --text-color: #2e3436;
                        --background-color: #f6f5f4;
                        --alt-background-color: #edeeef;
                        --link-color: #0d71de;
                        --blockquote-text-color: #747e85;
                        --blockquote-border-color: #d6d8da;
                        --header-border-color: #e1e2e4;
                        --hr-background-color: #d8dadd;
                        --table-tr-border-color: #bdc1c6;
                        --table-td-border-color: #d6d8da;
                        --kbd-text-color: #4e585e;
                        --kbd-background-color: #f1f1f1;
                        --kbd-border-color: #bdc1c6;
                        --kbd-shadow-color: #8c939a;
                    }

                    @media (prefers-color-scheme: dark) {
                        :root {
                            --text-color: #eeeeec;
                            --background-color: #353535;
                            --alt-background-color: #3a3a3a;
                            --link-color: #b5daff;
                            --blockquote-text-color: #a8a8a6;
                            --blockquote-border-color: #525252;
                            --header-border-color: #474747;
                            --hr-background-color: #505050;
                            --table-tr-border-color: #696969;
                            --table-td-border-color: #525252;
                            --kbd-text-color: #cececc;
                            --kbd-background-color: #3c3c3c;
                            --kbd-border-color: #696969;
                            --kbd-shadow-color: #979797;
                        }
                    }"""
        CUSTOM_STYLE = """
            --text-color: {view_fg_color};
            --background-color: {view_fg_color};
            --alt-background-color: {view_bg_color};
            --link-color: {accent_fg_color};
            --blockquote-text-color: {card_fg_color};
            --blockquote-border-color: {card_bg_color};
            --header-border-color: #e1e2e4;
            --hr-background-color: #d8dadd;
            --table-tr-border-color: #bdc1c6;
            --table-td-border-color: #d6d8da;
            --kbd-text-color: #4e585e;
            --kbd-background-color: #f1f1f1;
            --kbd-border-color: #bdc1c6;
            --kbd-shadow-color: #8c939a;
        """

        if os.path.exists(os.path.expanduser("~/.config/gtk-4.0/gtk.css")):
            variables, palette, css = self.parse_css(os.path.expanduser("~/.config/gtk-4.0/gtk.css"))
            print(variables, palette, css)
            theme_css = ":root {\n" + CUSTOM_STYLE.format(**variables) + " \n}\n" + css
        else:
            theme_css = ADWAITA_STYLE
        self.show(TEMPLATE.replace("{response}", response).replace("{theme_css}", theme_css), Step.LOAD_WEBVIEW)

    def on_ask_action(self, widget, _):
        """Callback for the app.ask action."""

        self.prompt = self.win.prompt_text_view.get_buffer().props.text.strip()

        if self.prompt == "" or self.prompt is None:  # empty prompt
            return
        else:
            self.win.spinner.start()
            self.win.ask_button.set_visible(False)
            self.win.wait_button.set_visible(True)
            self.provider = self.win.provider_selector.props.selected

            def thread_run():
                try:
                    response = self.ask(self.prompt)
                except GLib.Error as e:
                    response = e.message
                GLib.idle_add(cleanup, response)

            def cleanup(response):
                self.win.spinner.stop()
                self.win.ask_button.set_visible(True)
                self.win.wait_button.set_visible(False)
                GLib.idle_add(self.update_response, response)
                self.t.join()
                if self.clear_after_send:
                    self.win.prompt_text_view.get_buffer().set_text("")

            self.t = threading.Thread(target=thread_run)
            self.t.start()

    # def on_speak_action(self, widget, _):
    #     """Callback for the app.speak action."""
    #     print("app.speak action activated")
    #
    #     try:
    #
    #         with NamedTemporaryFile() as file_to_play:
    #
    #             tts = gTTS(self.win.bot_text_view.get_buffer().props.text)
    #             tts.write_to_fp(file_to_play)
    #             file_to_play.seek(0)
    #             self._play_audio(file_to_play.name)
    #     except Exception as exc:
    #         print(exc)
    #
    # def _play_audio(self, path):
    #     uri = "file://" + path
    #     self.player.set_property("uri", uri)
    #     self.pipeline.add(self.player)
    #     self.pipeline.set_state(Gst.State.PLAYING)
    #     self.player.set_state(Gst.State.PLAYING)
    #
    # def on_listen_action(self, widget, _):
    #     """Callback for the app.listen action."""
    #     print("app.listen action activated")

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version):
    """The application's entry point."""
    app = BavarderApplication()
    return app.run(sys.argv)
