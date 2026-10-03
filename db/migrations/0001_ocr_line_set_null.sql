ALTER TABLE "generation_replacements" DROP CONSTRAINT "generation_replacements_ocr_line_id_ocr_lines_id_fk";
--> statement-breakpoint
ALTER TABLE "generation_replacements" ADD CONSTRAINT "generation_replacements_ocr_line_id_ocr_lines_id_fk" FOREIGN KEY ("ocr_line_id") REFERENCES "public"."ocr_lines"("id") ON DELETE set null ON UPDATE no action;