
class Constants:

    @staticmethod
    def clearance_mm() -> float:
        """
        Should provide enough clearance to move parts past each other, may require some force.
        """
        return 0.15

    @staticmethod
    def perfboard_pitch() -> float:
        return 2.54

    @staticmethod
    def golden_ratio() -> float:
        return 1.61803398875
