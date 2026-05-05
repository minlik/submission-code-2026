from typing import Optional, List
from dataclasses import dataclass
import sys
import linecache


__all__ = ["Stacktrace", "StackFrame"]


@dataclass
class StackFrame(object):
    filename: str
    lineno: int
    name: str
    line: str
    in_code: bool


class Stacktrace(object):

    @staticmethod
    def print_exec(
        e: Exception, 
        code: Optional[str] = None, 
        filename: Optional[str] = None,
        mode: str = "fullstack",
    ):
        print("\n".join(Stacktrace.format_exception(e, code, filename, mode)), file=sys.stderr)

    @staticmethod
    def format_exception(
        e: Exception, 
        code: Optional[str] = None, 
        filename: Optional[str] = None,
        mode: str = "fullstack",
    ) -> List[str]:
        assert mode in ["fullstack", "codestack", "erroronly"]
        outputs = []
        if "stack" in mode:
            outputs.append(f"Traceback (most recent call last):")
            frames = Stacktrace.extract_stack_frames(e.__traceback__, code, filename)
            if mode == "codestack":
                frames = [f for f in frames if f.in_code]
            for f in frames:
                outputs.append(f"  File \"{f.filename}\", line {f.lineno}, in {f.name}")
                outputs.append(f"    {f.line.strip()}")
            
        outputs.append(f"{type(e).__name__}: {str(e)}")
        return outputs


    @staticmethod
    def extract_stack_frames(
        trace,
        code: Optional[str] = None, 
        filename: Optional[str] = None
    ) -> List[StackFrame]:
        code_lines = code.splitlines() if code is not None else []
        frames = []
        while trace:
            if trace.tb_frame.f_code.co_filename == filename:
                line = code_lines[trace.tb_lineno - 1] if trace.tb_lineno <= len(code_lines) else ''
                in_code = True
            else:
                line = linecache.getline(trace.tb_frame.f_code.co_filename, trace.tb_lineno)
                in_code = False

            frames.append(StackFrame(
                filename=trace.tb_frame.f_code.co_filename,
                lineno=trace.tb_lineno,
                name=trace.tb_frame.f_code.co_name,
                line=line,
                in_code=in_code
            ))

            trace = trace.tb_next

        return frames