import os
import struct
from subprocess import Popen
import sys


########################################################################################################################
############################################################################################## Used by parent process ##

###### Public

___all__ = ['launch']


def launch():
    this_script = os.path.abspath(__file__)

    parent_in, child_out = os.pipe()
    child_in, parent_out = os.pipe()

    try:
        env = {'PYTHONPATH': os.environ['PYTHONPATH']}
    except KeyError:
        env = {}

    face_position_subprocess = Popen(
        args=('python', this_script, str(child_in), str(child_out)),
        executable=sys.executable,
        stdout=sys.stdout,
        stderr=sys.stderr,
        env=env)

    def cleanup_child():
        """Send a terminate request to the child, wait for it to exit, then close all file descriptors."""
        _terminate(parent_out)

        face_position_subprocess.wait()

        # Close all open file descriptors.
        for fd in parent_out, parent_in, child_out, child_in:
            os.close(fd)

    get_face_position = lambda: _query(parent_out, parent_in, error_handler=sys.exit)

    return get_face_position, cleanup_child


###### Private

def _terminate(fd_write):
    """Notify the other end of the pipe that we're about to stop the program."""
    os.write(fd_write, _TERMINATE_MSG)


def _query(fd_write, fd_read, error_handler=None):
    """Query the other end of the pipe for the current face position."""

    # Notify the other end of the pipe that we're ready to receive the next face position.
    os.write(fd_write, _REQUEST_MSG)

    # Wait for the face position to be sent.
    read_buffer = os.read(fd_read, _RESPONSE_PACKING_SIZE)

    # If the pipe was closed and an error handler is specified, run the error handler.
    if not read_buffer and error_handler:
        error_handler()

    # Otherwise, unpack the response into a tuple and return it.
    return _unpack_response(read_buffer)


def _unpack_response(response):
    """Unpack the response """
    unpacked = struct.unpack(_RESPONSE_PACKING_FORMAT, response)
    return unpacked if unpacked != _INVALID_FACE else None


########################################################################################################################
################################################################################## Used by parent and child processes ##

_INVALID_FACE = (0.0, 0.0, 0.0)
_RESPONSE_PACKING_FORMAT = '>fff'
_RESPONSE_PACKING_SIZE = 12
_REQUEST_MSG = chr(0)
_TERMINATE_MSG = chr(1)


########################################################################################################################
############################################################################################### Used by child process ##

def _pack_response(x, y, z):
    return struct.pack(_RESPONSE_PACKING_FORMAT, x, y, z)


def _detect_faces(image, cascade, storage):
    """
    From: http://www.calebmadrigal.com/facial-detection-opencv-python/
    """
    import cv

    faces = []
    # Recommended settings for fast real-time processing, see:
    #   http://opencv.willowgarage.com/documentation/python/objdetect_cascade_classification.html
    detected = cv.HaarDetectObjects(image, cascade, storage, 1.2, 2, cv.CV_HAAR_DO_CANNY_PRUNING, (100, 100))
    if detected:
        for (x, y, w, h), n in detected:
            faces.append((x, y, w, h))
    return faces


def _answer_queries(fd_read, fd_write):
    import cv

    HAAR_CASCADE_PATH = "/usr/local/share/OpenCV/haarcascades/haarcascade_frontalface_default.xml"
    CAMERA_INDEX = 0

    cv.NamedWindow("Video", cv.CV_WINDOW_AUTOSIZE)

    capture = cv.CaptureFromCAM(CAMERA_INDEX)
    storage = cv.CreateMemStorage()
    cascade = cv.Load(HAAR_CASCADE_PATH)
    image = cv.QueryFrame(capture)
    image_w, image_h = cv.GetSize(image)

    def convert_first_face_to_point(faces):
        if faces:
            face_x, face_y, face_w, face_h = faces[0]

            #          0 ----- 'x' ----- 1
            #        0 +-----------------+
            #        | |                 |
            #       'z'|     camera      |
            #        | |                 |
            #        1 +-----------------+
            #         0 (face height matches camera height)
            #        /
            #      'y'
            #      /
            #     1 (infinitely far away)

            # Right between the eyes.
            x = (face_x + face_w / 2.0) / image_w
            # Distance from screen in no particular unit.
            y = 1.0 - float(face_h) / image_h
            # Roughly eye level.
            z = (face_y + face_h / 2.0) / image_h
        else:
            x, y, z = _INVALID_FACE

        return x, y, z

    def pack_and_send_response(x, y, z):
        response = _pack_response(x, y, z)
        os.write(fd_write, response)

    def take_picture_and_detect_faces():
        image = cv.QueryFrame(capture)
        return _detect_faces(image, cascade, storage)

    def send_face_position():
        faces = take_picture_and_detect_faces()
        x, y, z = convert_first_face_to_point(faces)
        pack_and_send_response(x, y, z)

    def read_request():
        # Wait for request to come in.
        msg = os.read(fd_read, 1)

        # If the channel has been closed or a close is requested, terminate.
        if not msg or msg == _TERMINATE_MSG:
            return False

        # Otherwise, business as usual.
        return True

    while True:
        if not read_request():
            break
        send_face_position()


if __name__ == '__main__':
    fd_read, fd_write = int(sys.argv[1]), int(sys.argv[2])

    _answer_queries(fd_read, fd_write)

    for fd in fd_write, fd_read:
        os.close(fd)
