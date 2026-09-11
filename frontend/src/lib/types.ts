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

export interface SessionInfo {
	id: string;
	created_at: string;
	last_seen_at: string;
	ip: string | null;
	user_agent: string | null;
	auth_method: string;
	current: boolean;
}
