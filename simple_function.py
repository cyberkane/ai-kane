# -*- coding: utf-8 -*-
import math

def human_volume(weight=None, height=None):
    """
    Calculates the volume of a human.

    Args:
        weight (float): Weight of the person in kilograms.
        height (float): Height of the person in meters.

    Returns:
        float: Volume of the person in cubic meters.
    """
    if weight is None or height is None:
        raise ValueError("Weight and height are required")

    return weight / 1000 * (height ** 3) / 1000

print("Первый вес:", human_volume(weight=70, height=1.75))

def another_human_volume(weight, height):
    return weight / 1000 * (height ** 3) / 1000
    
print("Другой вес и высота:", another_human_volume(weight=70, height=1.63))