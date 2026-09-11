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
	totp_enabled: boolean;
}

export interface TotpStatus {
	enabled: boolean;
	enabled_at: string | null;
	recovery_codes_left: number;
}

export interface TotpSetup {
	secret: string;
	uri: string;
	qr_svg: string;
}

export interface Area {
	id: string;
	name: string;
	color: string;
	icon: string;
	sort_order: number;
	open_count: number;
	role: string;
	/** Kalender: Wochentage als Bitmaske (Bit 0 = Montag) und sichtbare Stunden. */
	week_days: number;
	day_start: number;
	day_end: number;
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
	/** Verknüpfter Termin, z. B. bei der Folgeaufgabe eines Telefontermins. */
	event_id: string | null;
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
	/** Aus einem abonnierten Kalender (z. B. Streamo) – nur dort änderbar. */
	read_only: boolean;
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
	calendar_id: string | null;
	calendar_name: string | null;
	read_only: boolean;
	tags: string[];
	attendees: Attendee[];
	reminders: number[];
	sequence: number;
	contact: Contact | null;
	channel: Channel | null;
	agreed_on: string | null;
	agreed_with: string;
	priority: Priority;
	tasks: LinkedTask[];
	created_at: string;
	updated_at: string;
}

export type Channel = 'phone' | 'in_person' | 'mail' | 'other';

export interface Contact {
	id: string;
	name: string;
	company: string;
	phone: string;
	email: string;
	address: string;
	use_count: number;
	last_used_at: string | null;
}

export interface LinkedTask {
	id: string;
	title: string;
	due_date: string | null;
	status: TaskStatus;
}

export interface AppointmentResult {
	event: EventDetail;
	task: Task | null;
	contact: Contact | null;
	conflicts: Conflict[];
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

export interface PushDevice {
	id: string;
	user_agent: string | null;
	created_at: string;
	last_success_at: string | null;
}

export interface ExternalCalendarInfo {
	id: string;
	name: string;
	host: string;
	area_id: string;
	area_name: string;
	refresh_minutes: number;
	enabled: boolean;
	event_count: number;
	last_synced_at: string | null;
	last_success_at: string | null;
	last_error: string | null;
	created_at: string;
}

export interface PasskeyInfo {
	id: string;
	name: string;
	created_at: string;
	last_used_at: string | null;
	/** In iCloud-Schlüsselbund, Google-Passwortmanager & Co. synchronisiert */
	backed_up: boolean;
	device_type: string;
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
