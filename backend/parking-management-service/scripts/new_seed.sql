-- New test data for camera 5003 (invalid spots)
-- Safe to run more than once: it recreates test containers/calibrations for the new camera.

BEGIN;

INSERT INTO segments_configs (id, name, horizontal_segments, vertical_segments, description, created_at)
VALUES
    (1, 'default_8x5', 8, 5, 'Стандартная конфигурация для камер 16:9', '2026-03-18 16:25:50.119425'::timestamptz),
    (2, 'wide_12x6', 12, 6, 'Для широкоугольных камер', '2026-03-18 16:25:50.119425'::timestamptz),
    (3, 'narrow_6x4', 6, 4, 'Для камер с узким обзором', '2026-03-18 16:25:50.119425'::timestamptz)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    horizontal_segments = EXCLUDED.horizontal_segments,
    vertical_segments = EXCLUDED.vertical_segments,
    description = EXCLUDED.description;

SELECT setval(
    pg_get_serial_sequence('segments_configs', 'id'),
    GREATEST((SELECT COALESCE(MAX(id), 1) FROM segments_configs), 1),
    true
);

WITH parking AS (
    INSERT INTO parkings_table (
        address,
        total_spots,
        available_spots,
        name,
        coordinates,
        boundaries,
        is_active,
        settings
    )
    SELECT
        'Тестовые данные Сергея',
        4,
        4,
        'Парковка Сергея 5003',
        '{"lat": 0, "lng": 0}'::json,
        '{"points": [[0, 0], [500, 0], [500, 265], [0, 265]]}'::json,
        true,
        '{"source": "sergey_dump"}'::json
    WHERE NOT EXISTS (
        SELECT 1 FROM parkings_table WHERE name = 'Парковка Сергея 5003'
    )
    RETURNING id
),
selected_parking AS (
    SELECT id FROM parking
    UNION ALL
    SELECT id FROM parkings_table WHERE name = 'Парковка Сергея 5003'
    LIMIT 1
),
camera_upsert AS (
    INSERT INTO camera_table (
        rtsp_url,
        status,
        position_x,
        position_y,
        is_calibrated,
        monitored_spot_ids,
        segments_config_id,
        parking_id
    )
    SELECT
        '/app/videos/new_test.ts',
        'ACTIVE',
        0,
        0,
        true,
        '[]'::json,
        1,
        selected_parking.id
    FROM selected_parking
    WHERE NOT EXISTS (
        SELECT 1
        FROM camera_table
        WHERE rtsp_url = '/app/videos/new_test.ts'
    )
    RETURNING id, parking_id
),
selected_camera AS (
    SELECT id, parking_id FROM camera_upsert
    UNION ALL
    SELECT id, parking_id
    FROM camera_table
    WHERE rtsp_url = '/app/videos/new_test.ts'
    LIMIT 1
),
spot_base AS (
    INSERT INTO spots_table (
        spot_number,
        spot_type,
        spot_status,
        spot_coordinates,
        occupied_since,
        current_vehicle_id,
        parking_id
    )
    SELECT
        'SG-5003-1',
        'STANDARD',
        'FREE',
        '{"points": [[120, 120], [420, 120], [420, 280], [120, 280]], "center_x": 270, "center_y": 200}'::json,
        NULL,
        NULL,
        selected_camera.parking_id
    FROM selected_camera
    ON CONFLICT (parking_id, spot_number) DO UPDATE SET
        spot_status = 'FREE',
        spot_coordinates = EXCLUDED.spot_coordinates
    RETURNING id
),
spot_2 AS (
    INSERT INTO spots_table (
        spot_number,
        spot_type,
        spot_status,
        spot_coordinates,
        occupied_since,
        current_vehicle_id,
        parking_id
    )
    SELECT
        'SG-5003-2',
        'STANDARD',
        'FREE',
        '{"points": [[120, 300], [420, 300], [420, 460], [120, 460]], "center_x": 270, "center_y": 380}'::json,
        NULL,
        NULL,
        selected_camera.parking_id
    FROM selected_camera
    ON CONFLICT (parking_id, spot_number) DO UPDATE SET
        spot_status = 'FREE',
        spot_coordinates = EXCLUDED.spot_coordinates
    RETURNING id
),
spot_3 AS (
    INSERT INTO spots_table (
        spot_number,
        spot_type,
        spot_status,
        spot_coordinates,
        occupied_since,
        current_vehicle_id,
        parking_id
    )
    SELECT
        'SG-5003-3',
        'STANDARD',
        'FREE',
        '{"points": [[120, 480], [420, 480], [420, 640], [120, 640]], "center_x": 270, "center_y": 560}'::json,
        NULL,
        NULL,
        selected_camera.parking_id
    FROM selected_camera
    ON CONFLICT (parking_id, spot_number) DO UPDATE SET
        spot_status = 'FREE',
        spot_coordinates = EXCLUDED.spot_coordinates
    RETURNING id
),
spot_4 AS (
    INSERT INTO spots_table (
        spot_number,
        spot_type,
        spot_status,
        spot_coordinates,
        occupied_since,
        current_vehicle_id,
        parking_id
    )
    SELECT
        'SG-5003-4',
        'DISABLED',
        'FREE',
        '{"points": [[120, 660], [420, 660], [420, 820], [120, 820]], "center_x": 270, "center_y": 740}'::json,
        NULL,
        NULL,
        selected_camera.parking_id
    FROM selected_camera
    ON CONFLICT (parking_id, spot_number) DO UPDATE SET
        spot_status = 'FREE',
        spot_coordinates = EXCLUDED.spot_coordinates
    RETURNING id
),
cleanup AS (
    DELETE FROM parking_containers
    WHERE camera_id = (SELECT id FROM selected_camera)
      AND name IN ('BaseContainer2', 'Container5', 'Container6', 'Container7')
)
INSERT INTO parking_containers (
    camera_id,
    spot_id,
    name,
    length,
    width,
    height,
    ground_points,
    upper_points,
    image_points,
    is_base,
    created_at,
    updated_at
)
SELECT
    selected_camera.id,
    (SELECT id FROM spot_base),
    'BaseContainer2',
    4.60,
    2.60,
    2.00,
    '[[0,0,0],[4.6,0,0],[4.6,0,2.6],[0,0,2.6]]'::json,
    '[[0,2,0],[4.6,2,0],[4.6,2,2.6],[0,2,2.6]]'::json,
    '[[296.4,1133.8],[2.0,641.1],[543.4,498.6],[1019.6,722.2]]'::json,
    true,
    NOW(),
    NOW()
FROM selected_camera
UNION ALL
SELECT
    selected_camera.id,
    (SELECT id FROM spot_2),
    'Container5',
    4.60,
    2.65,
    2.00,
    '[[0.001,0,2.6],[4.601,0,2.604],[4.599,0,5.254],[-0.001,0,5.25]]'::json,
    '[[0.001,2,2.6],[4.601,2,2.604],[4.599,2,5.254],[-0.001,2,5.25]]'::json,
    '[[1025.5,720.2],[553.3,496.6],[926.7,395.7],[1369.4,528.3]]'::json,
    false,
    NOW(),
    NOW()
FROM selected_camera
UNION ALL
SELECT
    selected_camera.id,
    (SELECT id FROM spot_3),
    'Container6',
    4.60,
    2.65,
    2.00,
    '[[0.005,0,5.259],[4.605,0,5.257],[4.607,0,7.907],[0.007,0,7.909]]'::json,
    '[[0.005,2,5.259],[4.605,2,5.257],[4.607,2,7.907],[0.007,2,7.909]]'::json,
    '[[1371.3,526.3],[936.6,391.8],[1209.3,326.5],[1598.6,401.7]]'::json,
    false,
    NOW(),
    NOW()
FROM selected_camera
UNION ALL
SELECT
    selected_camera.id,
    (SELECT id FROM spot_4),
    'Container7',
    5.20,
    2.65,
    2.00,
    '[[-0.595,0,7.927],[4.605,0,7.92],[4.609,0,10.57],[-0.591,0,10.577]]'::json,
    '[[-0.595,2,7.927],[4.605,2,7.92],[4.609,2,10.57],[-0.591,2,10.577]]'::json,
    '[[1675.6,415.5],[1223.1,322.5],[1393.1,277.0],[1774.4,342.3]]'::json,
    false,
    NOW(),
    NOW()
FROM selected_camera;

INSERT INTO camera_calibrations (
    container_id,
    camera_matrix,
    rvec,
    tvec,
    dist_coeffs,
    image_shape,
    created_at,
    homography
)
SELECT
    parking_containers.id,
    '[[2304,0,1152],[0,2304,648],[0,0,1]]'::json,
    '[-1.2524,0.66167,-2.6888]'::json,
    '[-2.9315,1.3638,9.5752]'::json,
    '[0,0,0,0]'::json,
    '[1296,2304]'::json,
    NOW(),
    NULL::json
FROM parking_containers
WHERE name = 'BaseContainer2'
  AND camera_id = (
      SELECT id
      FROM camera_table
      WHERE rtsp_url = '/app/videos/new_test.ts'
      LIMIT 1
  );

INSERT INTO parking_spots_current (spot_id, status, vehicle_track_id, parked_since, last_updated)
SELECT id, 'free', NULL, NULL, NOW()
FROM parking_containers
WHERE camera_id = (
    SELECT id
    FROM camera_table
    WHERE rtsp_url = '/app/videos/new_test.ts'
    LIMIT 1
)
ON CONFLICT (spot_id) DO UPDATE SET
    status = EXCLUDED.status,
    vehicle_track_id = NULL,
    parked_since = NULL,
    last_updated = NOW();

UPDATE camera_table
SET monitored_spot_ids = (
        SELECT COALESCE(json_agg(id ORDER BY id), '[]'::json)
        FROM parking_containers
        WHERE camera_id = camera_table.id
    ),
    is_calibrated = true,
    segments_config_id = 1
WHERE rtsp_url = '/app/videos/new_test.ts';

COMMIT;