export type Priority = 0 | 1 | 2 | 3;
export type TaskStatus = 'open' | 'done' | 'archived';
export type Locale = 'de' | 'en';

export interface Meta {
	version: string;
	setup_required: boolean;
	rp_id: string;
}

export interface User {
	id: string;
	email: string;
	display_name: string;
	is_admin: boolean;
	timezone: string;
	locale: Locale;
}

export interface Area {
	id: string;
	name: string;
	color: string;
	icon: string;
	sort_order: number;
	open_count: number;
	role: string;
}

export interface ChecklistItem {
	id: string;
	text: string;
	done: boolean;
}

export interface Task {
	id: string;
	area_id: string;
	title: string;
	notes: string;
	notes_html: string;
	due_date: string | null;
	due_time: string | null;
	priority: Priority;
	status: TaskStatus;
	completed_at: string | null;
	tags: string[];
	recurrence: string | null;
	source: string;
	sort_order: number;
	checklist: ChecklistItem[];
	created_at: string;
	updated_at: string;
}

export interface TaskSection {
	key: string;
	title?: string;
	href?: string;
	tasks: Task[];
}

export interface CompleteResult {
	task: Task;
	next: Task | null;
}

export interface QuickAddPreview {
	title: string;
	due_date: string | null;
	due_time: string | null;
	priority: Priority;
	tags: string[];
	area_id: string | null;
	area_name: string | null;
	area_unknown: boolean;
	recurrence: string | null;
	tokens: string[];
}

export type EventStatus = 'tentative' | 'confirmed' | 'cancelled';
export type EventScope = 'this' | 'following' | 'all';

export interface Occurrence {
	key: string;
	event_id: string;
	series_id: string | null;
	recurrence_id: string | null;
	area_id: string;
	title: string;
	location: string;
	all_day: boolean;
	status: EventStatus;
	is_fixed: boolean;
	recurring: boolean;
	tags: string[];
	start: string;
	end: string;
	start_local: string;
	end_local: string;
}

export interface Attendee {
	name: string;
	email: string | null;
}

export interface EventDetail {
	id: string;
	uid: string;
	series_id: string | null;
	recurrence_id: string | null;
	area_id: string;
	title: string;
	description: string;
	description_html: string;
	location: string;
	url: string;
	all_day: boolean;
	start_date: string;
	start_time: string | null;
	end_date: string;
	end_time: string | null;
	tzid: string;
	rrule: string | null;
	status: EventStatus;
	transparency: 'opaque' | 'transparent';
	is_fixed: boolean;
	source: string;
	tags: string[];
	attendees: Attendee[];
	reminders: number[];
	sequence: number;
	created_at: string;
	updated_at: string;
}

export interface Conflict {
	key: string;
	title: string;
	start_local: string;
	end_local: string;
}

export interface EventWriteResult {
	event: EventDetail;
	conflicts: Conflict[];
}

export interface EventSearchResult {
	id: string;
	title: string;
	location: string;
	all_day: boolean;
	recurring: boolean;
	start_local: string;
}

export interface SearchResult {
	tasks: Task[];
	events: EventSearchResult[];
}

export type EventEditorRequest =
	| { mode: 'edit'; eventId: string; occurrence: string | null }
	| { mode: 'new'; date: string; time?: string; allDay?: boolean };

export type FeedDetail = 'full' | 'title' | 'busy';

export interface FeedInfo {
	id: string;
	name: string;
	area_id: string | null;
	area_name: string | null;
	detail: FeedDetail;
	created_at: string;
	last_used_at: string | null;
}

export interface FeedCreated {
	feed: FeedInfo;
	url: string;
	webcal_url: string;
}

export interface SessionInfo {
	id: string;
	created_at: string;
	last_seen_at: string;
	ip: string | null;
	user_agent: string | null;
	auth_method: string;
	current: boolean;
}
