import argparse
import csv
import math
from pathlib import Path


def read_trajectory(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        samples = [
            (float(row["time_s"]), float(row["position_m"]))
            for row in csv.DictReader(stream)
        ]
    if len(samples) < 2 or samples[0] != (0.0, 0.0):
        raise ValueError("Each trajectory needs at least two samples and must start at (0, 0).")
    if any(not math.isfinite(value) for sample in samples for value in sample):
        raise ValueError("Trajectory values must be finite.")
    if any(right[0] <= left[0] for left, right in zip(samples, samples[1:])):
        raise ValueError("Sample times must increase strictly.")
    return samples


def main():
    parser = argparse.ArgumentParser(description="Validate an incline-motion model against measured trajectories.")
    parser.add_argument("calibration", type=Path)
    parser.add_argument("validation", type=Path)
    parser.add_argument("--calibration-angle", type=float, required=True)
    parser.add_argument("--validation-angle", type=float, required=True)
    parser.add_argument("--output", type=Path, default=Path("comparison.csv"))
    args = parser.parse_args()

    if args.calibration.resolve() == args.validation.resolve():
        parser.error("Use separate recordings for calibration and validation.")
    if args.output.resolve() in {args.calibration.resolve(), args.validation.resolve()}:
        parser.error("Output must be separate from both input files.")
    if not all(0 < angle < 90 for angle in (args.calibration_angle, args.validation_angle)):
        parser.error("Incline angles must be between 0 and 90 degrees.")
    try:
        calibration = read_trajectory(args.calibration)
        validation = read_trajectory(args.validation)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))

    gravity = 9.80665
    angle = math.radians(args.calibration_angle)
    # Fit displacement = acceleration * t^2 / 2 through the release point.
    acceleration = 2 * sum(t**2 * x for t, x in calibration) / sum(t**4 for t, _ in calibration)
    friction = (math.sin(angle) - acceleration / gravity) / math.cos(angle)
    if acceleration <= 0 or friction < 0:
        parser.error("Calibration data is incompatible with downhill sliding and nonnegative friction.")

    angle = math.radians(args.validation_angle)
    acceleration = gravity * (math.sin(angle) - friction * math.cos(angle))
    if acceleration <= 0:
        parser.error("The fitted model does not predict downhill sliding at the validation angle.")

    rows = []
    for time, observed in validation:
        predicted = 0.5 * acceleration * time**2
        rows.append((time, observed, predicted, predicted - observed))

    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("time_s", "observed_m", "predicted_m", "error_m"))
        writer.writerows(rows)

    print(f"Fitted kinetic friction: {friction:.5f}")
    print(f"Position MAE: {1000 * sum(abs(row[3]) for row in rows) / len(rows):.3f} mm")
    print(f"Position RMSE: {1000 * math.sqrt(sum(row[3]**2 for row in rows) / len(rows)):.3f} mm")


if __name__ == "__main__":
    main()
