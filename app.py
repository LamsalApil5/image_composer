from flask import Flask, redirect, request, render_template, send_file, url_for
from PIL import Image
import io
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/temp'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def compress_image(image, output_format='JPEG', target_size_bytes=30 * 1024):
    quality = 85
    step = 5
    min_quality = 10
    img_io = io.BytesIO()

    if output_format.upper() == 'JPEG':
        image = image.convert("RGB")  # JPEG requires RGB

        # Save once with initial quality
        image.save(img_io, format='JPEG', optimize=True, quality=quality)

        # If image is already small enough, keep it as is
        if img_io.tell() <= target_size_bytes:
            img_io.seek(0)
            return img_io, quality

        # Otherwise, reduce quality gradually
        while img_io.tell() > target_size_bytes and quality > min_quality:
            quality -= step
            img_io = io.BytesIO()
            image.save(img_io, format='JPEG', optimize=True, quality=quality)

        img_io.seek(0)
        return img_io, quality

    elif output_format.upper() == 'PNG':
        # PNG compression is lossless
        image.save(img_io, format='PNG', optimize=True, compress_level=9)
        img_io.seek(0)
        return img_io, None

    else:
        raise ValueError('Unsupported format')

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['image']
        output_format = request.form.get('format', 'JPEG').upper()

        if not file:
            return render_template('index.html', error='No file uploaded.')

        filename = secure_filename(file.filename)
        original_path = os.path.join(app.config['UPLOAD_FOLDER'], 'original.' + filename.split('.')[-1])
        file.save(original_path)

        image = Image.open(original_path)
        original_info = {
            'name': filename,
            'format': image.format,
            'size': os.path.getsize(original_path),
            'width': image.width,
            'height': image.height
        }

        compressed_io, final_quality = compress_image(image, output_format=output_format)
        compressed_ext = 'jpg' if output_format == 'JPEG' else 'png'
        compressed_path = os.path.join(app.config['UPLOAD_FOLDER'], 'compressed.' + compressed_ext)
        with open(compressed_path, 'wb') as f:
            f.write(compressed_io.read())

        compressed_image = Image.open(compressed_path)
        compressed_info = {
            'size': os.path.getsize(compressed_path),
            'width': compressed_image.width,
            'height': compressed_image.height,
            'quality': final_quality
        }

        return render_template('index.html',
                               original=original_info,
                               compressed=compressed_info,
                               show_preview=True,
                               output_format=output_format)

    return render_template('index.html')

@app.route('/download')
def download():
    # Try to find compressed image with known extensions
    for ext in ['jpg', 'png']:
        path = os.path.join(app.config['UPLOAD_FOLDER'], f'compressed.{ext}')
        if os.path.exists(path):
            response = send_file(path, as_attachment=True, download_name=f'compressed.{ext}')
            # After sending the file, redirect back to index to reset
            @response.call_on_close
            def cleanup():
                # Optionally delete the files to clean temp folder
                try:
                    os.remove(path)
                    original_path_jpg = os.path.join(app.config['UPLOAD_FOLDER'], 'original.jpg')
                    original_path_png = os.path.join(app.config['UPLOAD_FOLDER'], 'original.png')
                    if os.path.exists(original_path_jpg):
                        os.remove(original_path_jpg)
                    if os.path.exists(original_path_png):
                        os.remove(original_path_png)
                except Exception as e:
                    print("Cleanup error:", e)

            return response

    # If no file found
    return redirect(url_for('index'))

# ✅ Moved to the end of the file
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
