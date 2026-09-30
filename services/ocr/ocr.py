import sys
import json
from rapidocr_onnxruntime import RapidOCR

def main():
    if len(sys.argv) < 2:
        print("Usage: ocr.py <image_path>", file=sys.stderr)
        sys.exit(1)
        
    image_path = sys.argv[1]
    
    try:
        engine = RapidOCR()
        result, elapse = engine(image_path)
    except Exception as e:
        print(f"Error running OCR: {e}", file=sys.stderr)
        sys.exit(1)

    lines = []
    if result:
        for item in result:
            box, text, conf = item[0], item[1], item[2]
            
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            
            x = int(min(xs))
            y = int(min(ys))
            width = int(max(xs)) - x
            height = int(max(ys)) - y
            
            if width <= 0 or height <= 0:
                continue

            lines.append({
                "text": text,
                "confidence": float(conf),
                "x": x,
                "y": y,
                "width": width,
                "height": height
            })
            
    print(json.dumps({"lines": lines}))
    
if __name__ == "__main__":
    main()
