import streamlit as st
import re
from collections import namedtuple

scene_file = st.file_uploader("Scene file", type="scn")
if not scene_file:
    st.stop()

class ConfigLine(namedtuple("ConfigLine", 'path value')):
    def match_context(self, path):
        return self.path.startswith(path)
    
    def match_setting(self, path):
        return self.path.endswith(path)
    
    @property
    def path_parts(self):
        return self.path.split("/")[1:]
    
    def __str__(self) -> str:
        return f"{self.path} {self.value}"


def parse_cfgline(line):
    """Parse config lines into parts and values.
    Example:
    
    /ch/01/config xxxxx xxxx

    becomes
    
    # ConfigLine(path=['ch', '01', 'config'], value='xxxxx xxxx'])
    ConfigLine(path="/ch/01/config", value="xxxxx xxxx")
    """
    parts = line.split(" ", 1)
    path = parts[0]#.split("/")[1:]
    value = parts[1]
    return ConfigLine(path, value)

# Match channel number and name
# e.g.,
# /ch/01/config "Acoustic Gtr" 23 RD 1
# should match 01 and "Acoustic Gtr"
channel_pattern = re.compile(r"/ch/(\d+)/config\s+\"(.+)\"")

existing_names = {}
lines = scene_file.read().decode('utf-8').splitlines()
# The file starts with a header line
# example:
# #4.0# "Choir" "" %000000000 1    
header = lines.pop(0)
parsed_lines = [parse_cfgline(line) for line in lines]
for line in lines:
    if match := channel_pattern.match(line):
        channel_number = match.group(1)
        channel_name = match.group(2)
        existing_names[f"ch{channel_number}"] = channel_name

for i in range(32):
    num = str(i+1).zfill(2)
    existing_names[f"ch{num}"] = existing_names.get(f"ch{num}", f"Ch {num}")

st.header("New Channels")
new_channels = {}

available = list(existing_names.keys())
for i in range(32):
    num = str(i+1).zfill(2)
    key = f"ch{num}"
    if key in st.session_state:
        val = st.session_state[key]
        # When the available options changes, streamlit blanks out the selectbox.
        # So to avoid having to reselect everything, tell streamlit what the index should be.
        if val in available:
            # add 1 because we're going to add an empty option
            index = available.index(st.session_state[key]) + 1
        else:
            index = 0
            if val:
                st.warning(f"{val} already used")
    else:
        index = 0
    new_channel = st.selectbox(
        f"Channel {num}", [""] + available,
        key=key, index=index,
        format_func=lambda x: existing_names.get(x, ""))
    if new_channel:
        new_channels[new_channel] = key
        available.remove(new_channel)

# Regenerate the scene file
new_scene = [header]
for setting in parsed_lines:
    if setting.match_context("/ch"):
        prev_channel_number = setting.path_parts[1]
        key = f"ch{prev_channel_number}"
        if key not in new_channels:
             #st.write("Skipping channel ", prev_channel_number)
             continue
        new_channel_number = new_channels[key][2:]
        setting = ConfigLine(
            f"/ch/{new_channel_number}/{'/'.join(setting.path_parts[2:])}", setting.value)
    
    new_scene.append(str(setting))

st.write(new_channels)

st.download_button("Download new scene", "\n".join(new_scene), "scene.scn", mime="text/plain")
st.markdown("```" + "\n".join(new_scene) + "```")