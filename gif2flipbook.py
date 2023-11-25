import argparse
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple, cast

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfMerger
from tqdm import trange


def get_resized_dimensions(
    temp_dir: Path, border: int, no_size_increase: bool
) -> Tuple[int, int, float]:
    frame = Image.open(
        os.path.join(
            temp_dir,
            "0.png",
        )
    )

    # determine how gif should be resized.
    width, height = frame.size

    # 2550: width of 300ppi US letter page in pixels
    printable_width = 2550 / 2 - 2 * border
    # 3300: height of 300ppi US letter page in pixels
    # 150: space for page number text
    printable_height = 3300 / 2 - 2 * border - 150
    width_check = 1 - (width - printable_width) / width
    height_check = 1 - (height - printable_height) / height
    if width_check < 1 or height_check < 1:
        resize_factor = min([width_check, height_check])
    elif not no_size_increase and width_check > 1 and height_check > 1:
        resize_factor = min([width_check, height_check])
    else:
        resize_factor = 1

    # Get updated width and height
    frame = frame.resize(
        (
            math.floor(resize_factor * width),
            math.floor(resize_factor * height),
        )
    )
    width_resized, height_resized = frame.size

    return width_resized, height_resized, resize_factor


def get_number_image(number: int, numbers_font: ImageFont.FreeTypeFont) -> Image.Image:
    page_number_box = numbers_font.getbbox(str(number))
    number_image_size = (
        math.floor((page_number_box[2] - page_number_box[0]) * 2),
        math.floor((page_number_box[3] - page_number_box[1]) * 2),
    )
    number_image = Image.new("RGBA", number_image_size, (255, 255, 255, 0))
    number_image_editable = ImageDraw.Draw(number_image)
    number_image_editable.text(
        (
            math.floor(number_image_size[0] / 2),
            math.floor(number_image_size[1] / 2),
        ),
        str(number),
        font=numbers_font,
        fill="LightSlateGrey",
        anchor="mm",
    )
    return number_image


def paste_number_image(
    blank_canvas: Image.Image,
    number_image: Image.Image,
    border: int,
    frame_mod: int,
):
    width, height = number_image.size
    half_width = width / 2
    if frame_mod == 0:
        blank_canvas.paste(
            number_image.rotate(180),
            (
                math.floor(2550 * 0.25 - half_width),
                math.floor(3300 / 2 - border - height),
            ),
        )
    elif frame_mod == 1:
        blank_canvas.paste(
            number_image.rotate(180),
            (
                math.floor(2550 * 0.75 - half_width),
                math.floor(3300 / 2 - border - height),
            ),
        )
    elif frame_mod == 2:
        blank_canvas.paste(
            number_image,
            (
                math.floor(2550 * 0.25 - half_width),
                math.floor(3300 / 2 + border),
            ),
        )
    else:
        blank_canvas.paste(
            number_image,
            (
                math.floor(2550 * 0.75 - half_width),
                math.floor(3300 / 2 + border),
            ),
        )


def gif2pngs(
    _path_video: Path,
    temp_dir: Path,
) -> int:
    """Saves video as pngs into a dir. Returns amount of frames."""
    if _path_video.suffix in ["gif", "webp", "apng", "avif", "flif", "mng"]:
        # Can use PIL to open single images
        with Image.open(_path_video) as video_object:
            n_frames = video_object.n_frames
            try:
                for i_frame in range(video_object.n_frames):
                    video_object.seek(i_frame)
                    video_object.save(
                        os.path.join(
                            temp_dir,
                            f"{i_frame}.png",
                        )
                    )

            except Exception as e:
                print(str(e))
                sys.exit(
                    " File is not supported for flipbook generation."
                    + " Please use another file format such as GIF or MP4."
                )
    else:
        # Use cv2 to open video files
        import cv2

        video_object = cv2.VideoCapture(str(_path_video))
        success, frame = video_object.read()
        i_frame = 0
        while success:
            cv2.imwrite(
                os.path.join(
                    temp_dir,
                    f"{i_frame}.png",
                ),
                frame,
            )
            i_frame += 1
            success, frame = video_object.read()
        n_frames = i_frame

    return n_frames


def gif2flipbook(
    path_video: str,
    rotate: int = -90,
    no_lines: bool = False,
    border: int = 75,
    no_size_increase: bool = False,
    pdf_resolution: int = 200,
):
    """Convert a video into a pdf which can be printed as a flipbook.

    Parameters
    ----------
    path_video : str
        Path to the video to be converted.
    path_pdf : str, default=`None`
        Path for the pdf which will be generated, if `None` will use the same path
        as the input video with the extension changed to `.pdf`.
    rotate : int, default=`90`
        Rotate the video by the specified number of degrees.
    no_lines : bool, default=`False`
        Do not print the guiding lines on the flipbook pages.
    border : int, default=`75`
        Non-printable border at the top and bottom of the page (in pixels).
    """

    cwd = Path.cwd()
    numbers_font = ImageFont.truetype(os.path.join(cwd, "baskvl.ttf"), 60)

    _path_video = Path(path_video)

    # Determine output path
    output_path = Path(
        _path_video.parent,
        f"{_path_video.stem}.flipbook.pdf",
    )
    print(f"Output path: {output_path}")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)

        # 1. Convert video into pngs
        print(f"Reading images from: {str(_path_video)}")
        n_frames = gif2pngs(_path_video, temp_dir)
        print(f"Number of frames: {n_frames}")

        # 2. Paste pngs into pdf

        # Get image dimensions for pasting on pdf
        width_resized, height_resized, resize_factor = get_resized_dimensions(
            temp_dir, border, no_size_increase
        )
        dimensions = (width_resized, height_resized)

        # Determine where to place the image on the pdf
        pos_left_top = (border, border)
        pos_right_top = (2550 - border - width_resized, border)
        pos_left_bot = (border, 3300 - border - height_resized)
        pos_right_bot = (2550 - border - width_resized, 3300 - border - height_resized)
        positions = {
            0: pos_left_top,
            1: pos_right_top,
            2: pos_left_bot,
            3: pos_right_bot,
        }

        # Loop through pdfs and paste frames on it
        n_pdfs = math.ceil(n_frames / 4)
        idx_frame = 0
        part_pdf_paths = list()
        for idx_pdf in trange(n_pdfs, desc="Pasting images"):
            # Load blank canvas (white US letter JPEG image, 300 ppi, 2550x3300 px)
            blank_canvas = Image.open(os.path.join(cwd, "blank_canvas.jpg")).convert(
                "RGB"
            )
            blank_canvas_editable = ImageDraw.Draw(blank_canvas)

            # Paste frames on canvas
            for frame_mod in range(4):
                frame_i = Image.open(
                    os.path.join(
                        temp_dir,
                        f"{idx_frame}.png",
                    )
                ).convert("RGB")

                # resize image
                if resize_factor != 1:
                    frame_i = frame_i.resize(
                        dimensions, resample=Image.Resampling.LANCZOS
                    )

                # rotate image
                if rotate != 0:
                    frame_i = frame_i.rotate(rotate)

                # paste image
                if frame_mod in [0, 1]:
                    frame_i = frame_i.rotate(180)
                blank_canvas.paste(frame_i, cast(Tuple[int, int], positions[frame_mod]))

                # paste number
                number_image = get_number_image(idx_frame, numbers_font)
                paste_number_image(
                    blank_canvas=blank_canvas,
                    number_image=number_image,
                    border=border,
                    frame_mod=frame_mod,
                )

                idx_frame += 1
                if idx_frame == n_frames:
                    break

            # Draw lines on canvas
            if not no_lines:
                blank_canvas_editable.line(
                    [(2550 / 2, 0), (2550 / 2, 3300)], fill="Gainsboro", width=5
                )
                blank_canvas_editable.line(
                    [(0, 3300 / 2), (2550, 3300 / 2)], fill="Gainsboro", width=5
                )

            # scale pdf
            if pdf_resolution != 300:
                blank_canvas = blank_canvas.resize(
                    (
                        round(2550 * pdf_resolution / 300),
                        round(3300 * pdf_resolution / 300),
                    ),
                    resample=Image.Resampling.LANCZOS,
                )

            # Save intermittent pdf, merging all PIL pdf gets too big in memory
            part_pdf_path = os.path.join(
                temp_dir,
                f"{idx_pdf}.pdf",
            )
            part_pdf_paths.append(part_pdf_path)
            blank_canvas.save(
                part_pdf_path,
                resolution=pdf_resolution,
            )

        # Merge pdfs into one
        print("Merging pdfs")
        pdf_merger = PdfMerger()
        for part_pdf_path in part_pdf_paths:
            pdf_merger.append(part_pdf_path)
        pdf_merger.write(output_path)
        print(f"Output pdf: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="gif2flipbook",
        description=(
            "Python script to convert a video into a pdf which can be printed as a flipbook."
        ),
    )
    parser.add_argument(
        "path_video", type=str, help="path to the video to be converted."
    )
    parser.add_argument(
        "--rotate",
        type=int,
        default=-90,
        help="Rotate the video by the specified number of degrees.",
    )
    parser.add_argument(
        "--no_lines",
        action="store_true",
        help="Do not print the guiding lines on the flipbook pages.",
    )
    parser.add_argument(
        "--border",
        type=int,
        default=75,
        help="Non-printable border at the top and bottom of the page (in inches).",
    )
    parser.add_argument(
        "--no_size_increase",
        action="store_true",
        help="Do not increase the size of the images to fit within the available space.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=None,
        help="Frames per second (fps) of the video to be converted.",
    )
    parser.add_argument(
        "--pdf_resolution",
        type=int,
        default=200,
        help="Resolution of the pdf to be generated (in dpi).",
    )
    args = parser.parse_args()

    gif2flipbook(
        path_video=args.path_video,
        rotate=args.rotate,
        no_lines=args.no_lines,
        border=args.border,
        no_size_increase=args.no_size_increase,
        pdf_resolution=args.pdf_resolution,
    )
