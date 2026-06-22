WHEELBARROW_PARAMS = {
    'wheel_radius': 350,
    'track_width': 0,
    'effective_track_width': 500,
    'com_height': 900,
    'mass': 40,
    'payload_mass': 200,
    'human_force': 500,
    'approach_angle': 3,
    'historical_source': '《三国志·蜀书·诸葛亮传》《后汉书》',
}

CARRIAGE_PARAMS = {
    'wheel_radius': 700,
    'num_wheels': 4,
    'axle_width': 1500,
    'com_height': 1500,
    'mass': 300,
    'payload_mass': 600,
    'horse_pull_force': 2000,
    'num_horses': 2,
    'suspension_stiffness': 5000,
    'suspension_damping': 2000,
    'approach_angle': 6,
    'historical_source': '《周礼·考工记》《史记·平准书》',
}

TERRAIN_PROFILES = {
    'flat': {'slope': 0, 'roughness': 0, 'obstacle_density': 0, 'friction': 0.8},
    'gentle_slope': {'slope': 10, 'roughness': 5, 'obstacle_density': 0, 'friction': 0.7},
    'steep_slope': {'slope': 25, 'roughness': 10, 'obstacle_density': 5, 'friction': 0.6},
    'rocky': {'slope': 15, 'roughness': 50, 'obstacle_density': 30, 'friction': 0.5},
    'muddy': {'slope': 5, 'roughness': 5, 'obstacle_density': 0, 'friction': 0.3},
    'stairs': {'slope': 30, 'roughness': 20, 'obstacle_density': 50, 'friction': 0.7},
    'obstacle': {'slope': 5, 'roughness': 30, 'obstacle_density': 60, 'friction': 0.6},
}

HISTORICAL_SOURCES = {
    '木牛流马': {
        'source': '《三国志·蜀书·后主传》《诸葛亮集·作木牛流马法》',
        'description': '诸葛亮创制的木制机械运输工具，用于蜀汉时期',
    },
    '独轮车': {
        'source': '《三国志·蜀书·诸葛亮传》《后汉书》',
        'description': '古代单轮人力运输工具，相传由诸葛亮发明或改进',
    },
    '马车': {
        'source': '《周礼·考工记》《史记·平准书》',
        'description': '古代畜力运输工具，商周时期已广泛使用',
    },
}
