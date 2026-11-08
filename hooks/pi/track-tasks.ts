/**
 * track-tasks — pi extension for track-tasks skill notations (^task:...).
 *
 * All logic lives in Python (`main.py hook ...`, `main.py notation complete`);
 * this file only wires pi's lifecycle events and editor to it.
 *
 * - session_start: fetch the notation legend once, load the notation key and
 *   this project's task handles, and register autocomplete.
 * - before_agent_start: on the first user prompt of a session, add the legend;
 *   on every user prompt, add the expanded forms of any notations.
 * - autocomplete: the first character of the notation key (^) triggers it.
 *   Typing `^` offers the key (`^task:`); after `^task:` it offers short codes,
 *   slugs and bucket names, filtered in memory, so typing never waits on Python.
 *
 * Context is returned as a `message` (added at the end of the conversation),
 * never by editing the system prompt, so the cached prompt prefix stays valid.
 *
 * Installed by: main.py hooks install --target pi
 */

import { spawnSync } from "node:child_process";
import * as os from "node:os";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import {
	type AutocompleteItem,
	type AutocompleteProvider,
	type AutocompleteSuggestions,
	fuzzyFilter,
} from "@earendil-works/pi-tui";

const skillsHome = process.env.SKILLS_HOME || path.join(os.homedir(), ".agents", "skills");
const skillDir = path.join(skillsHome, "track-tasks-skill");
const python = path.join(skillDir, ".venv", "bin", "python3");
const mainPy = path.join(skillDir, "scripts", "main.py");
const MAX_SUGGESTIONS = 20;

type Handle = { value: string; description: string };
type Completion = { key: string; skill: string; description: string; handles: Handle[] };

function runTrackTasks(args: string[], input = ""): string {
	const result = spawnSync(python, [mainPy, ...args, "--cwd", process.cwd()], {
		input,
		encoding: "utf8",
		timeout: 5000,
	});
	if (result.status !== 0 || typeof result.stdout !== "string") return "";
	return result.stdout.trim();
}

function runHook(event: "session-start" | "prompt", input = ""): string {
	return runTrackTasks(["hook", event, "--format", "text"], input);
}

function loadCompletion(): Completion | undefined {
	try {
		const completion = JSON.parse(runTrackTasks(["notation", "complete"])) as Completion;
		return completion.key ? completion : undefined;
	} catch {
		return undefined;
	}
}

/** The whitespace-delimited token ending at the cursor. */
function tokenBeforeCursor(lines: string[], cursorLine: number, cursorCol: number): string {
	const text = (lines[cursorLine] ?? "").slice(0, cursorCol);
	return text.match(/(?:^|\s)(\S*)$/)?.[1] ?? "";
}

function handleItems(completion: Completion, query: string): AutocompleteItem[] {
	const { key, handles } = completion;
	const matches = query
		? [
				...handles.filter((h) => h.value.toLowerCase().startsWith(query.toLowerCase())),
				...fuzzyFilter(handles, query, (h) => `${h.value} ${h.description}`),
			]
		: handles;
	const unique = [...new Map(matches.map((h) => [h.value, h])).values()];
	return unique.slice(0, MAX_SUGGESTIONS).map((h) => ({
		value: `${key}:${h.value}`,
		label: h.value,
		description: h.description,
	}));
}

function createNotationProvider(current: AutocompleteProvider, completion: Completion): AutocompleteProvider {
	const { key, skill, description } = completion;
	const trigger = key[0];

	const suggest = (token: string): AutocompleteSuggestions | null => {
		if (!token.startsWith(trigger)) return null;
		if (token.startsWith(`${key}:`)) {
			const items = handleItems(completion, token.slice(key.length + 1));
			return items.length ? { items, prefix: token } : null;
		}
		if (key.startsWith(token)) {
			return { items: [{ value: `${key}:`, label: key, description: `${skill}: ${description}` }], prefix: token };
		}
		return null;
	};

	return {
		triggerCharacters: [...new Set([...(current.triggerCharacters ?? []), trigger])],

		async getSuggestions(lines, cursorLine, cursorCol, options) {
			const token = tokenBeforeCursor(lines, cursorLine, cursorCol);
			const ours = suggest(token);
			if (!ours) return current.getSuggestions(lines, cursorLine, cursorCol, options);
			if (token.startsWith(`${key}:`)) return ours;
			// A bare `^` can start another skill's key too (topology's `^top`):
			// offer every provider's keys, not just ours.
			const theirs = await current.getSuggestions(lines, cursorLine, cursorCol, options);
			return theirs && theirs.prefix === ours.prefix ? { ...ours, items: [...ours.items, ...theirs.items] } : ours;
		},

		applyCompletion(lines, cursorLine, cursorCol, item, prefix) {
			if (!prefix.startsWith(trigger) || !item.value.startsWith(key)) {
				return current.applyCompletion(lines, cursorLine, cursorCol, item, prefix);
			}
			// `^task:` keeps the cursor on the token so handles are offered next;
			// a full notation gets a trailing space.
			const line = lines[cursorLine] ?? "";
			const before = line.slice(0, cursorCol - prefix.length);
			const after = line.slice(cursorCol);
			const insert = item.value.endsWith(":") ? item.value : `${item.value} `;
			const next = [...lines];
			next[cursorLine] = before + insert + after;
			return { lines: next, cursorLine, cursorCol: before.length + insert.length };
		},

		shouldTriggerFileCompletion(lines, cursorLine, cursorCol) {
			return current.shouldTriggerFileCompletion?.(lines, cursorLine, cursorCol) ?? true;
		},
	};
}

export default function trackTasksExtension(pi: ExtensionAPI) {
	let legend = "";
	let legendSent = false;

	pi.on("session_start", async (_event, ctx) => {
		legend = runHook("session-start");
		legendSent = false;

		const completion = loadCompletion();
		if (completion) {
			ctx.ui?.addAutocompleteProvider?.((current) => createNotationProvider(current, completion));
		}
	});

	pi.on("before_agent_start", async (event) => {
		if (event.messageType !== "user") return;

		const parts: string[] = [];
		if (!legendSent && legend) {
			parts.push(legend);
			legendSent = true;
		}
		const expanded = runHook("prompt", event.prompt);
		if (expanded) parts.push(expanded);
		if (parts.length === 0) return;

		return {
			message: {
				customType: "track-tasks-context",
				content: parts.join("\n\n"),
				display: Boolean(expanded),
			},
		};
	});
}
