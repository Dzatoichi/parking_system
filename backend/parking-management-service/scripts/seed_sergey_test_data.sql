-- Test data from Sergey's dump.sql, mapped to the current parking_system schema.
-- Safe to run more than once: it recreates only Sergey's test containers/calibrations.

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
        3,
        3,
        'Парковка Сергея 5005',
        '{"lat": 0, "lng": 0}'::json,
        '{"points": [[0, 0], [500, 0], [500, 265], [0, 265]]}'::json,
        true,
        '{"source": "sergey_dump"}'::json
    WHERE NOT EXISTS (
        SELECT 1 FROM parkings_table WHERE name = 'Парковка Сергея 5005'
    )
    RETURNING id
),
selected_parking AS (
    SELECT id FROM parking
    UNION ALL
    SELECT id FROM parkings_table WHERE name = 'Парковка Сергея 5005'
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
        '/app/videos/test.ts',
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
        WHERE rtsp_url = '/app/videos/test.ts'
    )
    RETURNING id, parking_id
),
selected_camera AS (
    SELECT id, parking_id FROM camera_upsert
    UNION ALL
    SELECT id, parking_id
    FROM camera_table
    WHERE rtsp_url = '/app/videos/test.ts'
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
        'SG-5005-1',
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
        'SG-5005-2',
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
        'SG-5005-3',
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
cleanup AS (
    DELETE FROM parking_containers
    WHERE camera_id = (SELECT id FROM selected_camera)
      AND name IN ('BaseContainer', 'Container2', 'Container3')
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
    'BaseContainer',
    5,
    2.65,
    2,
    '[[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [5.0, 0.0, 2.6500000953674316], [0.0, 0.0, 2.6500000953674316]]'::json,
    '[[0.0, 2.0, 0.0], [5.0, 2.0, 0.0], [5.0, 2.0, 2.6500000953674316], [0.0, 2.0, 2.6500000953674316]]'::json,
    '[[995.9000244140625, 714.2999877929688], [351.70001220703125, 536.2000122070312], [701.5, 401.70001220703125], [1252.800048828125, 482.79998779296875]]'::json,
    true,
    '2026-06-02 13:27:38.501593'::timestamptz,
    '2026-06-02 14:04:16.927763'::timestamptz
FROM selected_camera
UNION ALL
SELECT
    selected_camera.id,
    (SELECT id FROM spot_2),
    'Container2',
    5,
    2.65,
    2,
    '[[0.0, 0.0, 2.6549999713897705], [5.0, 0.0, 2.6679999828338623], [4.993000030517578, 0.0, 5.317999839782715], [-0.007000000216066837, 0.0, 5.304999828338623]]'::json,
    '[[0.0, 2.0, 2.6549999713897705], [5.0, 2.0, 2.6679999828338623], [4.993000030517578, 2.0, 5.317999839782715], [-0.007000000216066837, 2.0, 5.304999828338623]]'::json,
    '[[1256.699951171875, 476.79998779296875], [713.2999877929688, 395.70001220703125], [922.7999877929688, 316.6000061035156], [1403.0, 352.20001220703125]]'::json,
    false,
    '2026-06-02 13:27:38.501593'::timestamptz,
    '2026-06-02 13:31:19.110873'::timestamptz
FROM selected_camera
UNION ALL
SELECT
    selected_camera.id,
    (SELECT id FROM spot_3),
    'Container3',
    5,
    2.65,
    2,
    '[[-0.0020000000949949026, 0.0, 5.304999828338623], [4.998000144958496, 0.0, 5.323999881744385], [4.98799991607666, 0.0, 7.973999977111816], [-0.012000000104308128, 0.0, 7.954999923706055]]'::json,
    '[[-0.0020000000949949026, 2.0, 5.304999828338623], [4.998000144958496, 2.0, 5.323999881744385], [4.98799991607666, 2.0, 7.973999977111816], [-0.012000000104308128, 2.0, 7.954999923706055]]'::json,
    '[[1406.9000244140625, 348.20001220703125], [932.7000122070312, 310.6000061035156], [1053.199951171875, 259.20001220703125], [1485.9000244140625, 286.8999938964844]]'::json,
    false,
    '2026-06-02 13:27:38.501593'::timestamptz,
    '2026-06-02 13:31:19.112965'::timestamptz
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
    '[[2304, 0, 1152], [0, 2304, 648], [0, 0, 1]]'::json,
    '[-0.8613, 0.69326, -2.8944]'::json,
    '[-0.85573, 0.069131, 13.417]'::json,
    '[0, 0, 0, 0]'::json,
    '[1296, 2304]'::json,
    '2026-06-02 19:12:39.618821'::timestamptz,
    NULL::json
FROM parking_containers
WHERE name = 'BaseContainer'
  AND camera_id = (
      SELECT id
      FROM camera_table
      WHERE rtsp_url = '/app/videos/test.ts'
      LIMIT 1
  )
UNION ALL
SELECT
    parking_containers.id,
    '[[2304, 0, 1152], [0, 2304, 648], [0, 0, 1]]'::json,
    '[-0.96983498, 0.76379882, -2.85309622]'::json,
    '[-0.8473698, 0.28023122, 11.53101627]'::json,
    '[0, 0, 0, 0]'::json,
    '[1296, 2304]'::json,
    '2026-06-02 14:40:05.102676'::timestamptz,
    NULL::json
FROM parking_containers
WHERE name = 'Container3'
  AND camera_id = (
      SELECT id
      FROM camera_table
      WHERE rtsp_url = '/app/videos/test.ts'
      LIMIT 1
  );

INSERT INTO parking_spots_current (spot_id, status, vehicle_track_id, parked_since, last_updated)
SELECT id, 'free', NULL, NULL, NOW()
FROM parking_containers
WHERE camera_id = (
    SELECT id
    FROM camera_table
    WHERE rtsp_url = '/app/videos/test.ts'
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
WHERE rtsp_url = '/app/videos/test.ts';

COMMIT;
