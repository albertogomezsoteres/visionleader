/// Static building data for the UFV campus: short display names and GPS
/// coordinates per building id. Mirrors the canonical IDs used by the
/// backend campus topology.
class BuildingLocations {
  BuildingLocations._();

  static const Map<int, String> names = {
    1: 'G',
    2: 'CD',
    3: 'H',
    4: 'P',
    5: 'O',
    6: 'M',
    7: 'N',
    8: 'CSQ',
    9: 'K',
    10: 'CSC',
    11: 'C',
    12: 'E',
    13: 'CM',
    14: 'LCB',
    15: 'Rodilla',
    16: 'Capilla',
  };

  static const Map<int, Map<String, double>> gps = {
    1:  {'lat': 40.441620952298344, 'lng': -3.833659413892564},
    2:  {'lat': 40.441395514019310, 'lng': -3.833515841347269},
    3:  {'lat': 40.44188726971171, 'lng': -3.834391097938894},
    4:  {'lat': 40.44298858275285, 'lng': -3.835530301598534},
    5:  {'lat': 40.44316885736018, 'lng': -3.835200228598359},
    6:  {'lat': 40.44240864976504, 'lng': -3.834946704494870},
    7:  {'lat': 40.44220340611667, 'lng': -3.835944009359643},
    8:  {'lat': 40.44183583314631, 'lng': -3.835627725992759},
    9:  {'lat': 40.44198871772325, 'lng': -3.835362731820506},
    10: {'lat': 40.44156909752000, 'lng': -3.835700385685151},
    11: {'lat': 40.44104538179100, 'lng': -3.834678875834694},
    12: {'lat': 40.43980926640134, 'lng': -3.835392650504404},
    13: {'lat': 40.43961734118567, 'lng': -3.833708655238037},
    14: {'lat': 40.43988083159466, 'lng': -3.833195763291739},
    15: {'lat': 40.44074823643942, 'lng': -3.833941069721472},
    16: {'lat': 40.44072231214621, 'lng': -3.833342641737906},
  };

  static String nameOf(int? buildingId) {
    if (buildingId == null) return '';
    return names[buildingId] ?? 'B$buildingId';
  }
}
