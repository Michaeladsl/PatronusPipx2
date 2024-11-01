import argparse
import json
import os
import sys
from typing import List, Dict, Optional

class ValidationError(Exception):
    pass

class Header:
    def __init__(self, version: int, width: int, height: int, timestamp: Optional[int] = None, 
                 command: Optional[str] = None, theme: Optional[Dict[str, str]] = None, 
                 title: Optional[str] = None, idle_time_limit: Optional[float] = None, 
                 env: Optional[Dict[str, str]] = None):
        self.version = version
        self.width = width
        self.height = height
        self.timestamp = timestamp
        self.command = command
        self.theme = theme or {}
        self.title = title
        self.idle_time_limit = idle_time_limit
        self.env = env or {}

    @staticmethod
    def validate(header, debug):
        if not header:
            if debug:
                raise ValidationError("header must not be nil")
            else:
                return False
        if header.version != 2:
            if debug:
                raise ValidationError("only casts with version 2 are valid")
            else:
                return False
        if header.width <= 0:
            if debug:
                raise ValidationError("a valid width (>0) must be specified")
            else:
                return False
        if header.height <= 0:
            if debug:
                raise ValidationError("a valid height (>0) must be specified")
            else:
                return False
        return True

class Event:
    def __init__(self, time: float, event_type: str, data: str):
        self.time = time
        self.type = event_type
        self.data = data

    @staticmethod
    def validate(event, debug):
        if not event:
            if debug:
                raise ValidationError("event must not be nil")
            else:
                return False
        if event.type not in ["i", "o"]:
            if debug:
                raise ValidationError("type must either be 'o' or 'i'")
            else:
                return False
        return True

class Cast:
    def __init__(self, header: Header, event_stream: List[Event]):
        self.header = header
        self.event_stream = event_stream

    @staticmethod
    def validate(cast, debug):
        if not cast:
            if debug:
                raise ValidationError("cast must not be nil")
            else:
                return False
        if not Header.validate(cast.header, debug):
            return False
        if not Cast.validate_event_stream(cast.event_stream, debug):
            return False
        return True

    @staticmethod
    def validate_event_stream(event_stream: List[Event], debug):
        last_time = -1
        for event in event_stream:
            if event.time < last_time:
                if debug:
                    raise ValidationError("events must be ordered by time")
                else:
                    return False
            if not Event.validate(event, debug):
                return False
            last_time = event.time
        return True

    @staticmethod
    def encode(writer, cast, debug):
        if not writer:
            if debug:
                raise ValidationError("a writer must be specified")
            else:
                return False
        if not cast:
            if debug:
                raise ValidationError("a cast must be specified")
            else:
                return False

        header_json = json.dumps(cast.header.__dict__)
        writer.write(header_json + '\n')

        for event in cast.event_stream:
            json.dump([event.time, event.type, event.data], writer)
            writer.write('\n')
        return True

    @staticmethod
    def decode(reader, debug):
        if not reader:
            if debug:
                raise ValidationError("reader must not be nil")
            else:
                return False

        try:
            first_line = reader.readline().strip()
            if not first_line:
                if debug:
                    raise ValidationError("Header line is empty")
                else:
                    return False
            header = json.loads(first_line)
            header_obj = Header(**header)
        except json.JSONDecodeError as e:
            if debug:
                raise ValidationError(f"Error decoding header: {e}")
            else:
                return False

        event_stream = []
        for line in reader:
            line = line.strip()
            if not line:
                continue
            try:
                event_data = json.loads(line)
                event = Event(event_data[0], event_data[1], event_data[2])
                event_stream.append(event)
            except json.JSONDecodeError as e:
                if debug:
                    raise ValidationError(f"Error decoding event: {e}")
                else:
                    return False

        cast = Cast(header_obj, event_stream)
        if not Cast.validate(cast, debug):
            return False
        return cast

class QuantizeRange:
    def __init__(self, from_: float, to: float):
        self.From = from_
        self.To = to

    def in_range(self, value: float) -> bool:
        return self.From <= value < self.To

    def range_overlaps(self, another: 'QuantizeRange') -> bool:
        return self.in_range(another.From) or self.in_range(another.To)

class QuantizeTransformation:
    def __init__(self, ranges: List[QuantizeRange]):
        self.ranges = ranges

    def transform(self, cast: Cast, debug):
        if not cast:
            if debug:
                raise ValidationError("cast must not be nil")
            else:
                return False
        if not cast.event_stream:
            if debug:
                raise ValidationError("event stream must not be empty")
            else:
                return False
        if not self.ranges:
            if debug:
                raise ValidationError("at least one quantization range must be specified")
            else:
                return False

        deltas = [0] * len(cast.event_stream)
        for i in range(len(cast.event_stream) - 1):
            delta = cast.event_stream[i + 1].time - cast.event_stream[i].time

            for q_range in self.ranges:
                if q_range.in_range(delta):
                    delta = q_range.From
                    break

            deltas[i] = delta

        for i in range(len(cast.event_stream) - 1):
            cast.event_stream[i + 1].time = cast.event_stream[i].time + deltas[i]

        return True

def parse_quantize_range(input: str, debug) -> QuantizeRange:
    parts = input.split(',')
    if len(parts) > 2:
        if debug:
            raise ValidationError("invalid range format: must be `value[,value]`")
        else:
            return None

    from_ = float(parts[0])
    to = float(parts[1]) if len(parts) == 2 else float('inf')

    if from_ < 0:
        if debug:
            raise ValidationError("constraint not verified: from >= 0")
        else:
            return None
    if to <= from_:
        if debug:
            raise ValidationError("constraint not verified: from < to")
        else:
            return None

    return QuantizeRange(from_, to)

def parse_quantize_ranges(inputs: List[str], debug) -> List[QuantizeRange]:
    ranges = []
    for input in inputs:
        range_ = parse_quantize_range(input, debug)
        if range_:
            ranges.append(range_)
    return ranges

class Transformer:
    def __init__(self, transformation: QuantizeTransformation, input_file: Optional[str], output_file: Optional[str], debug: bool):
        if not transformation:
            if debug:
                raise ValidationError("a transformation must be specified")
            else:
                return None
        
        self.transformation = transformation
        self.input_file = input_file
        self.output_file = output_file
        self.debug = debug

    def transform(self):
        try:
            if self.debug:
                print(f"Reading file: {self.input_file}")
            with open(self.input_file, 'r') as infile:
                cast = Cast.decode(infile, self.debug)
                if not cast:
                    return
                Cast.validate(cast, self.debug)
                self.transformation.transform(cast, self.debug)
            
            if self.debug:
                print(f"Writing file: {self.output_file}")
            with open(self.output_file, 'w') as outfile:
                Cast.encode(outfile, cast, self.debug)
        except Exception as e:
            if self.debug:
                raise ValidationError(f"Error processing file {self.input_file}: {e}")

def quantize_action(static_dir: str, debug: bool):
    input_dir = os.path.join(static_dir, 'splits')
    if debug:
        print(f"Input directory: {input_dir}")
    
    default_range = ["2"]
    quantize_ranges = parse_quantize_ranges(default_range, debug)
    transformation = QuantizeTransformation(quantize_ranges)

    for filename in os.listdir(input_dir):
        if filename.endswith(".cast"):
            input_path = os.path.join(input_dir, filename)
            output_path = input_path

            if debug:
                print(f"Processing file: {input_path}")
            try:
                transformer = Transformer(transformation, input_path, output_path, debug)
                transformer.transform()
            except ValidationError as e:
                print(f"ValidationError processing file {input_path}: {e}")
            except Exception as e:
                print(f"Unexpected error processing file {input_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Quantize Asciinema Casts in a directory.')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()

    home_dir = os.path.expanduser("~")
    static_dir = os.path.join(home_dir, ".local", ".patronus", "static")

    try:
        quantize_action(static_dir, args.debug)
    except ValidationError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()