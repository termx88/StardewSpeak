﻿using StardewValley;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace StardewSpeak
{
    public static class Serialization
    {
        public static dynamic SerializeAnimal(FarmAnimal animal) 
        {
            var position = new List<float> { animal.Position.X, animal.Position.Y };
            bool isMature = (int)animal.age >= (byte)animal.ageWhenMature;
            int currentProduce = animal.currentProduce.Value;
            bool readyForHarvest = isMature && currentProduce > 0;
            var center = new List<int> { animal.getStandingX(), animal.getStandingY() };
            return new
            {
                position,
                center,
                tileX = animal.getTileX(),
                tileY = animal.getTileY(),
                wasPet = animal.wasPet.Value,
                type = animal.type.Value,
                name = animal.Name,
                isMature,
                currentProduce,
                readyForHarvest,
                toolUsedForHarvest = animal.toolUsedForHarvest.Value,
                location = animal.currentLocation.NameOrUniqueName,
            };
        }
    }
}