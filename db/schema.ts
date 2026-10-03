import { integer, pgTable, real, text, timestamp } from "drizzle-orm/pg-core";

const createdAt = () => timestamp("created_at", { withTimezone: true }).notNull();

// A user signs in one of two ways: the passwordless local button (email set, no
// password) or a username and password. One of email or username is always set.
export const users = pgTable("users", {
	id: text("id").primaryKey(),
	email: text("email").unique(),
	username: text("username").unique(),
	passwordHash: text("password_hash"),
	name: text("name").notNull(),
	createdAt: createdAt(),
});

export const images = pgTable("images", {
	id: text("id").primaryKey(),
	userId: text("user_id").notNull().references(() => users.id),
	width: integer("width").notNull(),
	height: integer("height").notNull(),
	storageKey: text("storage_key").notNull(),
	createdAt: createdAt(),
});

export const ocrLines = pgTable("ocr_lines", {
	id: text("id").primaryKey(),
	imageId: text("image_id").notNull().references(() => images.id),
	text: text("text").notNull(),
	confidence: real("confidence").notNull(),
	x: integer("x").notNull(),
	y: integer("y").notNull(),
	width: integer("width").notNull(),
	height: integer("height").notNull(),
});

export const generations = pgTable("generations", {
	id: text("id").primaryKey(),
	userId: text("user_id").notNull().references(() => users.id),
	imageId: text("image_id").notNull().references(() => images.id),
	provider: text("provider").notNull(),
	model: text("model").notNull(),
	status: text("status").notNull(), // 'pending', 'succeeded', 'failed'
	outputKey: text("output_key"),
	error: text("error"),
	createdAt: createdAt(),
});

// The spec names no key for this table; rows are only ever read by generation.
export const generationReplacements = pgTable("generation_replacements", {
	generationId: text("generation_id").notNull().references(() => generations.id),
	// Detecting again replaces an image's lines; a past result keeps its own copy of the box.
	ocrLineId: text("ocr_line_id").references(() => ocrLines.id, { onDelete: "set null" }),
	fromText: text("from_text").notNull(),
	toText: text("to_text").notNull(),
	x: integer("x").notNull(),
	y: integer("y").notNull(),
	width: integer("width").notNull(),
	height: integer("height").notNull(),
});

export const creditLedger = pgTable("credit_ledger", {
	id: text("id").primaryKey(),
	userId: text("user_id").notNull().references(() => users.id),
	delta: integer("delta").notNull(),
	reason: text("reason").notNull(),
	generationId: text("generation_id").references(() => generations.id),
	stripeEventId: text("stripe_event_id"),
	createdAt: createdAt(),
});

export const stripeEvents = pgTable("stripe_events", {
	id: text("id").primaryKey(),
	receivedAt: timestamp("received_at", { withTimezone: true }).notNull(),
});
