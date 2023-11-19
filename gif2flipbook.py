import argparse
import glob
import math
import os
import re
import shutil
import sys
from datetime import date
from typing import List, Tuple, cast

from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from pypdf import PdfMerger


def gif2flipbook(
    path_video: str,
    path_pdf: str | None = None,
    no_lines: bool = False,
    border: int = 75,
    no_size_increase: bool = False,
    fps: int | None = None,
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
    no_lines : bool, default=`False`
        Do not print the guiding lines on the flipbook pages.
    border : int, default=`75`
        Non-printable border at the top and bottom of the page (in pixels).
    """

    path_video = "/Volumes/opt/gif2flipbook/GIFS/hug.gif"

    cwd = os.getcwd()
    numbers_font = ImageFont.truetype(os.path.join(cwd, "baskvl.ttf"), 60)

    # 1. Convert video into pngs
    frame_durations: List[int] = []
    print(f"Reading video file: {path_video}")
    os.makedirs(os.path.join(cwd, "temporary"), exist_ok=True)
    with Image.open(path_video) as video_object:
        n_frames = video_object.n_frames
        try:
            for i_frame in range(video_object.n_frames):
                video_object.seek(i_frame)
                video_object.save(
                    os.path.join(
                        cwd,
                        "temporary",
                        f"{i_frame}.png",
                    )
                )
                frame_durations.append(int(video_object.info["duration"]))

        except Exception as e:
            print(str(e))
            sys.exit(
                " File is not supported for flipbook generation."
                + " Please use another file format such as GIF or MP4."
            )

    print(f"Number of frames: {n_frames}")

    # The dictionary "image_layout" contains keys mapping to the GIF indices and
    # values containing the string equivalent of the expressions required to determine
    # the x,y coordinates of the upper-left corner of the resized PNG images that will
    # be pasted onto "blank_canvas" or "blank_canvas_reverse". These cannot be determined
    # at this point, as the "resizing_factor" has not yet been calculated for each GIF.
    # An "eval()" method will be called later in the code upon obtaining this information,
    # effectively updating the values of "image_layout" for the corresponding x,y tuples.
    image_layout_dcts = {
        0: "(math.floor(8.5/4*300-width/2), border)",
        1: "(math.floor(8.5*0.75*300-width/2), border)",
        2: "(math.floor(8.5*0.75*300-width/2), math.floor(11*300-border-height))",
        3: "(math.floor(8.5/4*300-width/2), math.floor(11*300-border-height))",
    }

    # Each frame will be saved as an individual PDF document, and these will
    # be merged together after the end of the "for i in range(maximum_frame_number):" loop.
    pdf_number = 0

    width_resized = None
    height_resized = None
    resize_factor = None
    image_layout = None
    pdf_path = os.path.join(cwd, str(date.today()) + " flipbook", "PDF_parts")
    for i_frame in range(n_frames):
        # A blank canvas (white US letter JPEG image, with a resolution of 300 ppi (2550x3300 px))
        # is generated for the first GIF and will contain frames from 4 different GIFS.
        blank_canvas = Image.open(os.path.join(cwd, "blank_canvas.jpg")).convert("RGB")
        blank_canvas_editable = ImageDraw.Draw(blank_canvas)

        if i_frame == 0:
            frame = Image.open(
                os.path.join(
                    cwd,
                    "temporary",
                    f"{i_frame}.png",
                )
            )
            # The width and height of the frame will be checked against the available
            # space on the quarter of page on which it would be printed. If the image is
            # too small or too big, The default value of one for "resize_factor" would then
            # be the minimum between "width_check" and "height_check" to ensure that the resized
            # image will fit into the available space.
            width, height = frame.size

            width_check = 1 - (width - (8.5 / 2 * 300 - 2 * border)) / width
            height_check = 1 - (height - (4.5 * 300 - border)) / height
            if width_check < 1 or height_check < 1:
                resize_factor = min([width_check, height_check])
            elif not no_size_increase and width_check > 1 and height_check > 1:
                resize_factor = min([width_check, height_check])
            else:
                resize_factor = 1

            # Should the "resize_factor" not be equal to one, it means that the
            # PNG images need to be resized. The updated "width" and "height" x,y tuple
            # for the resized images will allow to position the images correctly on the flipbooks.
            frame = frame.resize(
                (
                    math.floor(resize_factor * width),
                    math.floor(resize_factor * height),
                )
            )
            width_resized, height_resized = frame.size

        dimensions = (cast(int, width_resized), cast(int, height_resized))

        # Now that the resized image dimensions are known for every GIF, the values
        # within the "image_layout" mapping to every GIF index (the keys of the dictionary)
        # will be updated using an "eval()" method. This only needs to be done for the first
        # run through the "for i in range(len(maximum_frame_number)):" loop, as the same
        # x, y tuples of the upper-left corners of the PNG images for every GIF will be
        # used throughout when pasting the images.
        if i_frame == 0:
            image_layout = eval(image_layout_dcts[0])

        frame_k = Image.open(
            os.path.join(
                cwd,
                "temporary",
                f"{i_frame}.png",
            )
        ).convert("RGB")

        # If "resize_factor" wasn't equal to one, it means that the PNG images for
        # the given GIF needs to be resized according to the updated width and height
        # values.
        if resize_factor != 1:
            frame_k = frame_k.resize(dimensions, resample=Image.Resampling.LANCZOS)

        # # The current frame index followed by the PIL image of the frame "frame_k"
        # # are appended to "FrameNumber_PILImage"
        # FrameNumber_PILImage[j].append([png_index_list[j][i], frame_k])

        blank_canvas.paste(frame_k.rotate(180), cast(Tuple[int, int], image_layout))

        # If the user hasn't passed in the "no_lines" argument, a horizontal and vertical
        # line will be drawn in order to divide the pages into quarters, which will facilitate
        # cutting the pages and assembling the flipbooks. These lines are only drawn on one side
        # of each sheet of paper.
        if not no_lines:
            blank_canvas_editable.line(
                [(2550 / 2, 0), (2550 / 2, 3300)], fill="Gainsboro", width=5
            )
            blank_canvas_editable.line(
                [(0, 3300 / 2), (2550, 3300 / 2)], fill="Gainsboro", width=5
            )

        # The frame number in the top of each quadrant in order to facilitate flipbook assembly.
        # The function below creates an image with the number text, which will be pasted over
        # the "blank_canvas" and "blank_canvas_reverse". Such a function is used instead of
        # writing directly on "blank_canvas" and "blank_canvas_reverse", since two of the
        # numbers need to be flipped.
        def text_image(number, numbers_font):
            page_number_box = numbers_font.getbbox(str(number))
            page_number_size = (
                math.floor((page_number_box[2] - page_number_box[0]) * 2),
                math.floor((page_number_box[3] - page_number_box[1]) * 2),
            )
            page_number_text = Image.new("RGBA", page_number_size, (255, 255, 255, 0))
            page_number_text_editable = ImageDraw.Draw(page_number_text)
            page_number_text_editable.text(
                (
                    math.floor(page_number_size[0] / 2),
                    math.floor(page_number_size[1] / 2),
                ),
                str(number),
                font=numbers_font,
                fill="LightSlateGrey",
                anchor="mm",
            )
            return page_number_text, page_number_size

        # The number text images are pasted onto "blank_canvas" in the top of each flipbook page,
        # with central horizontal alignment. The numbers of the upper two quadrants need to be
        # flipped (rotated 180 degrees), as the GIF frames are also flipped in these quadrants.
        # The page numbering corresponds to "maximum_frame_number-i", as the last frame is printed
        # first on odd-numbered pages of the PDF document.
        page_number_text, page_number_size = text_image(
            n_frames - i_frame, numbers_font
        )
        page_number_half_width = page_number_size[0] / 2
        blank_canvas.paste(
            page_number_text.rotate(180),
            (
                math.floor(2550 * 0.25 - page_number_half_width),
                math.floor(3300 / 2 - border - page_number_size[1]),
            ),
        )
        blank_canvas.paste(
            page_number_text.rotate(180),
            (
                math.floor(2550 * 0.75 - page_number_half_width),
                math.floor(3300 / 2 - border - page_number_size[1]),
            ),
        )
        blank_canvas.paste(
            page_number_text,
            (
                math.floor(2550 * 0.25 - page_number_half_width),
                math.floor(3300 / 2 + border),
            ),
        )
        blank_canvas.paste(
            page_number_text,
            (
                math.floor(2550 * 0.75 - page_number_half_width),
                math.floor(3300 / 2 + border),
            ),
        )

        # The "blank_canvas" and "blank_canvas_reverse" images are scaled according to the "pdf_resolution" dpi value,
        # taking into account that the initial canvas pixel size was 2550x3300 px for a 300 dpi canvas (typical quality
        # used in professional printing jobs).
        blank_canvas = blank_canvas.resize(
            (
                round(2550 * pdf_resolution / 300),
                round(3300 * pdf_resolution / 300),
            ),
            resample=Image.Resampling.LANCZOS,
        )

        # The path "pdf_path" will store the separate PDF files for each frame,
        # and the merging of the PDF files will be done using the PdfMerger Class
        # from the pyPDF module, as otherwise the assembly of a large PDF file is
        # quite lengthy towards the end of the process with PIL, as the file rapidly
        # becomes too large.
        if not os.path.exists(pdf_path):
            os.makedirs(pdf_path)
        pdf_number += 1
        blank_canvas.save(
            os.path.join(
                pdf_path,
                str(date.today()) + " flipbook-" + str(pdf_number) + ".pdf",
            ),
            resolution=pdf_resolution,
        )

    # The list returned by "glob" is sorted, such that the number suffixes directly
    # preceding the ".pdf" file extension may be assembled in sequence in the resulting list.
    # For example: "['2023-10-05 flipbook-1.pdf', '2023-10-05 flipbook-2.pdf',
    #'2023-10-05 flipbook-3.pdf']. This is important in order merge the PDF documents
    # in the correct order.
    pdf_files = sorted(
        glob.glob(os.path.join(pdf_path, "*.pdf")),
        key=lambda x: int(x.split("-")[-1].split(".")[0]),
    )
    pdf_merger = PdfMerger()
    for path in pdf_files:
        pdf_merger.append(path)
    pdf_merger.write(
        os.path.join(
            cwd, str(date.today()) + " flipbook", str(date.today()) + " flipbook.pdf"
        )
    )

    # The folder containing the separate PDF parts is deleted.
    shutil.rmtree(os.path.join(pdf_path))

    # Lastly, the "PNGS" folder containing the PNGs and its contents is deleted.
    shutil.rmtree(os.path.join(cwd, "temporary"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="gif2flipbook",
        description=(
            "Python script to convert a video into a pdf which can be printed as a flipbook."
        ),
    )
    parser.add_argument(
        "--path_video", type=str, help="path to the video to be converted."
    )
    # parser.add_argument(
    #     "path_pdf",
    #     type=str,
    #     nargs="?",
    #     default=None,
    #     required=False,
    #     help="Path for the pdf which will be generated.",
    # )
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
        # path_pdf=args.path_pdf,
        no_lines=args.no_lines,
        border=args.border,
        no_size_increase=args.no_size_increase,
        fps=args.fps,
        pdf_resolution=args.pdf_resolution,
    )
