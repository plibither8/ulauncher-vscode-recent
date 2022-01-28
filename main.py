import os
import os.path
import json
import pathlib
from types import prepare_class
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import (
	KeywordQueryEvent,
	ItemEnterEvent,
	PreferencesEvent,
	PreferencesUpdateEvent,
)
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.item.ExtensionSmallResultItem import ExtensionSmallResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from fuzzywuzzy import process, fuzz


class Utils:
	@staticmethod
	def get_path(filename, from_home=False):
		base_dir = pathlib.Path.home() if from_home else pathlib.Path(
			__file__).parent.absolute()
		return os.path.join(base_dir, filename)


class Code:
	path_dirs = ("/usr/bin", "/bin", "/snap/bin")
	variants = ("Code", "VSCodium")

	@staticmethod
	def find_code():
		for path in (pathlib.Path(path_dir) for path_dir in Code.path_dirs):
			for variant in Code.variants:
				installed_path = path / variant.lower()
				config_path = pathlib.Path.home() / ".config" / variant / "storage.json"
				if installed_path.exists() and config_path.exists():
					return installed_path, config_path,
		return False

	def is_installed(self):
		return bool(self.installed_path)

	def get_recents(self):
		recents = []

		storage = json.load(self.config_path.open("r"))
		openedPaths = storage["openedPathsList"]["entries"]
		for path in openedPaths:
			if "folderUri" in path:
				uri = path["folderUri"]
				icon = "folder"
				option = "--folder-uri"
			elif "fileUri" in path:
				uri = path["fileUri"]
				icon = "file"
				option = "--file-uri"
			elif "workspace" in path:
				uri = path["workspace"]["configPath"]
				icon = "workspace"
				option = "--file-uri"
			else:
				continue

			label = path["label"] if "label" in path else uri.split("/")[-1]
			recents.append({
				"uri":    uri,
				"label":  label,
				"icon":   icon,
				"option": option,
			})
		return recents

	def open_vscode(self, recent):
		if not self.is_installed():
			return
		os.system(f"{self.installed_path} {recent['option']} {recent['uri']}")

	def __init__(self):
		self.installed_path, self.config_path = self.find_code()


class CodeExtension(Extension):
	keyword = None
	code = None

	def __init__(self):
		super(CodeExtension, self).__init__()
		self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
		self.subscribe(ItemEnterEvent, ItemEnterEventListener())
		self.subscribe(PreferencesEvent, PreferencesEventListener())
		self.subscribe(PreferencesUpdateEvent, PreferencesUpdateEventListener())
		self.code = Code()

	def get_ext_result_items(self, query):
		query = query.lower() if query else ""
		recents = self.code.get_recents()
		items = []
		data = []
		label_matches = process.extract(query, choices=map(lambda c: c["label"], recents), limit=20, scorer=fuzz.partial_ratio)
		uri_matches = process.extract(query, choices=map(lambda c: c["uri"], recents), limit=20, scorer=fuzz.partial_ratio)
		for match in label_matches:
			recent = next((c for c in recents if c["label"] == match[0]), None)
			if (recent is not None and match[1] > 95):
				data.append(recent)
		for match in uri_matches:
			recent = next((c for c in recents if c["uri"] == match[0]), None)
			existing = next((c for c in data if c["uri"] == recent["uri"]), None)
			if (recent is not None and existing is None):
				data.append(recent)
		for recent in data[:20]:
			items.append(
				ExtensionSmallResultItem(
					icon=Utils.get_path(f"images/{recent['icon']}.svg"),
					name=recent["label"],
					on_enter=ExtensionCustomAction(recent),
				)
			)
		return items


class KeywordQueryEventListener(EventListener):
	def on_event(self, event, extension):
		items = []

		if not extension.code.is_installed():
			items.append(
				ExtensionResultItem(
					icon=Utils.get_path("images/icon.svg"),
					name="No VS Code?",
					description="Can't find the VS Code's `code` command in your system :(",
					highlightable=False,
					on_enter=HideWindowAction(),
				)
			)
			return RenderResultListAction(items)

		argument = event.get_argument() or ""
		items.extend(extension.get_ext_result_items(argument))
		return RenderResultListAction(items)


class ItemEnterEventListener(EventListener):
	def on_event(self, event, extension):
		recent = event.get_data()
		extension.code.open_vscode(recent)


class PreferencesEventListener(EventListener):
	def on_event(self, event, extension):
		extension.keyword = event.preferences["code_kw"]


class PreferencesUpdateEventListener(EventListener):
	def on_event(self, event, extension):
		if event.id == "code_kw":
			extension.keyword = event.new_value


if __name__ == "__main__":
	CodeExtension().run()
