// Erzeugt die PNG-App-Icons (ohne externe Abhängigkeiten).  Aufruf: node scripts/generate-icons.mjs
import { writeFileSync } from 'node:fs';
import { crc32, deflateSync } from 'node:zlib';

const ACCENT = [0x24, 0x59, 0xd6];
const WHITE = [0xff, 0xff, 0xff];
// Wie static/favicon.svg (viewBox 64): „TD“ zu 30 % weiß im Hintergrund, davor der Haken
// 17,35 → 27,45 → 47,22 mit einem Rand in Akzentfarbe, damit er sich von den Buchstaben abhebt.
const CHECK = [
	[17, 35],
	[27, 45],
	[47, 22]
];
const LETTER_ALPHA = 0.3;
const CHECK_WIDTH = 6.5;
const CHECK_BORDER = 12;

function inLetters(x, y) {
	// T: Balken 7–30 × 14–21, Stamm 15–22 × 14–50
	if (y >= 14 && y <= 21 && x >= 7 && x <= 30) return true;
	if (x >= 15 && x <= 22 && y >= 14 && y <= 50) return true;
	// D: Stamm 32–39 × 14–50, Bogen als Halbring um (39, 32) mit Radius 11–18
	if (x >= 32 && x <= 39 && y >= 14 && y <= 50) return true;
	const r = Math.hypot(x - 39, y - 32);
	return x >= 39 && r >= 11 && r <= 18;
}

function segmentDistance(px, py, [ax, ay], [bx, by]) {
	const dx = bx - ax;
	const dy = by - ay;
	const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)));
	return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

function insideRoundedRect(x, y, size, radius) {
	const cx = Math.min(Math.max(x, radius), size - radius);
	const cy = Math.min(Math.max(y, radius), size - radius);
	return Math.hypot(x - cx, y - cy) <= radius;
}

function render(size, { maskable }) {
	const radius = maskable ? 0 : size * (14 / 64);
	const scale = maskable ? 0.72 : 1; // Safe-Zone für maskierbare Icons
	const offset = (size * (1 - scale)) / 2;
	const unit = (size * scale) / 64; // Pixel je Einheit der 64er-viewBox
	const pixels = Buffer.alloc(size * size * 4);
	const samples = 4;
	for (let y = 0; y < size; y++) {
		for (let x = 0; x < size; x++) {
			let bg = 0;
			let white = 0; // Anteil Weiß über der Akzentfarbe
			for (let sy = 0; sy < samples; sy++) {
				for (let sx = 0; sx < samples; sx++) {
					const px = x + (sx + 0.5) / samples;
					const py = y + (sy + 0.5) / samples;
					if (!insideRoundedRect(px, py, size, radius)) continue;
					bg++;
					// In Koordinaten der viewBox umrechnen
					const vx = (px - offset) / unit;
					const vy = (py - offset) / unit;
					const d = Math.min(
						segmentDistance(vx, vy, CHECK[0], CHECK[1]),
						segmentDistance(vx, vy, CHECK[1], CHECK[2])
					);
					if (d <= CHECK_WIDTH / 2) white += 1;
					else if (d <= CHECK_BORDER / 2) white += 0;
					else if (inLetters(vx, vy)) white += LETTER_ALPHA;
				}
			}
			const total = samples * samples;
			const alpha = bg / total;
			const mix = bg ? white / bg : 0;
			const i = (y * size + x) * 4;
			for (let c = 0; c < 3; c++)
				pixels[i + c] = Math.round(ACCENT[c] * (1 - mix) + WHITE[c] * mix);
			pixels[i + 3] = Math.round(alpha * 255);
		}
	}
	return pixels;
}

function chunk(type, data) {
	const length = Buffer.alloc(4);
	length.writeUInt32BE(data.length);
	const typed = Buffer.concat([Buffer.from(type, 'ascii'), data]);
	const crc = Buffer.alloc(4);
	crc.writeUInt32BE(crc32(typed) >>> 0);
	return Buffer.concat([length, typed, crc]);
}

function png(size, options) {
	const pixels = render(size, options);
	const raw = Buffer.alloc(size * (size * 4 + 1));
	for (let y = 0; y < size; y++) {
		raw[y * (size * 4 + 1)] = 0;
		pixels.copy(raw, y * (size * 4 + 1) + 1, y * size * 4, (y + 1) * size * 4);
	}
	const header = Buffer.alloc(13);
	header.writeUInt32BE(size, 0);
	header.writeUInt32BE(size, 4);
	header.set([8, 6, 0, 0, 0], 8);
	return Buffer.concat([
		Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
		chunk('IHDR', header),
		chunk('IDAT', deflateSync(raw, { level: 9 })),
		chunk('IEND', Buffer.alloc(0))
	]);
}

writeFileSync('static/icon-192.png', png(192, { maskable: false }));
writeFileSync('static/icon-512.png', png(512, { maskable: false }));
writeFileSync('static/icon-maskable-512.png', png(512, { maskable: true }));
console.log('Icons erzeugt.');
