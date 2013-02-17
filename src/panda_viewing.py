# Built-in libraries
from math import pi, sin, cos

# External libraries
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.actor.Actor import Actor

# Local scripts
import face_position


class PandaApp(ShowBase):
    """
    A Panda3D app which animates a panda walking in place in the center of some greenery. This portion was adapted from:
        http://www.panda3d.org/manual/index.php/Loading_and_Animating_the_Panda_Model

    For each frame, the app determines the position of the user's face through the webcam and positions the camera in
    the scene accordingly.
    """

    def __init__(self, getFacePosition):
        ShowBase.__init__(self)

        self.getFacePosition = getFacePosition

        self.currentFace = (0.0, 0.0, 0.0)
        self.prvFaces = ([], [], [])
        self.avgOver = (5, 5, 5)

        # Load the environment model.
        self.environ = self.loader.loadModel("models/environment")
        # Re-parent the model to render.
        self.environ.reparentTo(self.render)
        # Apply scale and position transforms on the model.
        self.environ.setScale(0.25, 0.25, 0.25)
        self.environ.setPos(-8, 42, 0)

        # Add the orientCameraTask procedure to the task manager.
        self.taskMgr.add(self.orientCameraTask, "OrientCameraTask")

        # Load and transform the panda actor.
        self.pandaActor = Actor("models/panda-model",
                                {"walk": "models/panda-walk4"})
        self.pandaActor.setScale(0.005, 0.005, 0.005)
        self.pandaActor.reparentTo(self.render)
        # Loop its animation.
        self.pandaActor.loop("walk")

    def __reduceJitter(self):
        """The face calculation is prone jittering, so keep a running average of the last N frames."""
        avg = []
        for axisIndex, axisValue in enumerate(self.currentFace):
            maxHistory, axisHistory = self.avgOver[axisIndex], self.prvFaces[axisIndex]

            # Trim history to latest 'maxHistory' frames.
            if len(axisHistory) == maxHistory:
                axisHistory.pop(0)
            axisHistory.append(axisValue)

            axisAvg = sum(axisHistory) / len(axisHistory)
            avg.append(axisAvg)
        return avg

    def __calcCameraPos(self, facePos):
        """Calculate the camera position from the face position."""
        faceX, faceY, faceZ = facePos

        angleDegrees = (faceX + 0.5) * -60.0
        angleRadians = angleDegrees * (pi / 180.0)
        radius = -40.0 + 40.0 * (faceY + 1.0)

        cameraX = radius * sin(angleRadians)
        cameraY = radius * -cos(angleRadians)
        cameraZ = 10.0 + faceZ * -10.0

        return cameraX, cameraY, cameraZ

    # noinspection PyUnusedLocal
    def orientCameraTask(self, task):
        """Query the current position of the user's face."""
        self.currentFace = self.getFacePosition() or self.currentFace

        facePos = self.__reduceJitter()
        cameraPos = self.__calcCameraPos(facePos)

        self.camera.setPos(*cameraPos)
        self.camera.lookAt(self.pandaActor)

        return Task.cont


if __name__ == '__main__':
    getFacePosition, cleanupChild = face_position.launch()

    app = PandaApp(getFacePosition)
    app.finalExitCallbacks.append(cleanupChild)
    app.run()
