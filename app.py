import os
import tempfile
import streamlit as st
import ffmpeg

st.set_page_config(
    page_title="Video Compressor",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="expanded",
)

def get_file_size(file_path):
    """Return the file size in MB"""
    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024)

def get_video_info(input_file):
    """Get video information using ffprobe"""
    try:
        probe = ffmpeg.probe(input_file)
        video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        audio_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
        
        return {
            'width': int(video_info.get('width', 0)),
            'height': int(video_info.get('height', 0)),
            'duration': float(probe.get('format', {}).get('duration', 0)),
            'bitrate': int(probe.get('format', {}).get('bit_rate', 0)),
            'size': float(probe.get('format', {}).get('size', 0)),
            'has_audio': audio_info is not None
        }
    except Exception as e:
        st.error(f"Error getting video info: {e}")
        return None

def estimate_size(video_info, resolution, remove_audio, fps, bitrate):
    """Estimate compressed video size based on settings"""
    if not video_info:
        return None
    
    # Base calculation using bitrate
    bitrate_value = int(bitrate.replace('k', '000'))
    duration = video_info['duration']
    
    # Resolution factor (smaller resolution = smaller file)
    resolution_factor = 1.0
    if resolution != "original":
        target_width, target_height = map(int, resolution.split('x'))
        original_width, original_height = video_info['width'], video_info['height']
        original_area = original_width * original_height
        target_area = target_width * target_height
        
        if original_area > 0:
            resolution_factor = target_area / original_area
    
    # FPS factor (lower fps = smaller file)
    fps_factor = 1.0
    if fps != "original":
        # Assume 30fps as default if we can't determine actual fps
        original_fps = 30
        try:
            original_fps = eval(video_info.get('r_frame_rate', '30/1'))
        except:
            pass
        
        target_fps = int(fps)
        fps_factor = target_fps / original_fps
    
    # Audio factor (no audio = smaller file)
    audio_factor = 0.85 if remove_audio and video_info['has_audio'] else 1.0
    
    # Calculate estimated size in MB
    estimated_bytes = (bitrate_value / 8) * duration * resolution_factor * fps_factor * audio_factor
    estimated_mb = estimated_bytes / (1024 * 1024)
    
    return estimated_mb

def compress_video(input_file, output_file, resolution="1280x720", remove_audio=True, fps="24", bitrate="1000k", ffmpeg_path="ffmpeg"):
    """Compress the video with the given parameters"""
    try:
        # Start with the input file
        stream = ffmpeg.input(input_file)
        
        # Video settings
        video_stream = stream.video
        
        # Set resolution if not original
        if resolution != "original":
            width, height = map(int, resolution.split('x'))
            video_stream = video_stream.filter('scale', width, height)
        
        # Set framerate if not original
        if fps != "original":
            video_stream = video_stream.filter('fps', fps=int(fps))
        
        # Audio settings
        if not remove_audio:
            audio_stream = stream.audio
            output = ffmpeg.output(
                video_stream, 
                audio_stream, 
                output_file,
                video_bitrate=bitrate,
                **{'c:v': 'libx264'}
            )
        else:
            # No audio
            output = ffmpeg.output(
                video_stream, 
                output_file,
                video_bitrate=bitrate,
                **{'c:v': 'libx264', 'an': None}
            )
        
        # Run the ffmpeg command
        output = output.overwrite_output()
        ffmpeg.run(output, cmd=ffmpeg_path, quiet=True, overwrite_output=True)
        return True
    except Exception as e:
        st.error(f"Error compressing video: {e}")
        return False

def main():
    st.title("🎬 Video Compressor")
    st.write("Compress your videos for easy sharing on Discord, WhatsApp, and other platforms.")
    
    # Compression settings - applied to all videos
    st.sidebar.subheader("Compression Settings")
    
    resolution = st.sidebar.selectbox(
        "Resolution",
        options=["original", "1920x1080", "1280x720", "854x480", "640x360", "426x240"],
        index=2,  # Default to 1280x720
        key="resolution_select"
    )
    
    remove_audio = st.sidebar.checkbox(
        "Remove Audio", 
        value=True,
        key="remove_audio_checkbox"
    )
    
    fps = st.sidebar.selectbox(
        "Frame Rate (FPS)",
        options=["original", "24", "30", "60"],
        index=1,  # Default to 24 fps
        key="fps_select"
    )
    
    bitrate = st.sidebar.select_slider(
        "Video Quality",
        options=["500k", "1000k", "1500k", "2000k", "2500k", "3000k"],
        value="1000k",
        help="Lower values = smaller file size, higher values = better quality",
        key="bitrate_slider"
    )
    
    # File uploader - now supporting multiple files
    uploaded_files = st.sidebar.file_uploader(
        "Upload your videos", 
        type=["mp4", "avi", "mov", "mkv", "flv", "wmv"], 
        accept_multiple_files=True,
        key="video_uploader"
    )

    if uploaded_files:
        # Create a dictionary to store information about each video
        videos_data = {}
        
        # Process each uploaded file
        with st.status("Processing uploaded videos...", expanded=True) as status:
            for idx, uploaded_file in enumerate(uploaded_files):
                status.update(label=f"Processing {uploaded_file.name}...")
                
                # Create a unique key for this video
                video_key = f"video_{idx}_{uploaded_file.name}"
                
                # Create a temporary file to store the uploaded video
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    input_path = tmp_file.name
                
                # Get the file size and video information
                original_size = get_file_size(input_path)
                video_info = get_video_info(input_path)
                
                # Store the video information
                videos_data[video_key] = {
                    "name": uploaded_file.name,
                    "path": input_path,
                    "original_size": original_size,
                    "video_info": video_info,
                    "selected_for_compression": True  # Default to selected
                }
            
            # Complete the status when all videos are processed
            status.update(label="All videos processed successfully!", state="complete", expanded=False)
            
            # Display videos with options to select for compression
            st.subheader("Videos to Compress")
            
            # Determine number of columns (1-3 based on the number of videos)
            num_videos = len(videos_data)
            num_cols = min(max(1, num_videos), 3)  # At least 1, at most 3 columns
            
            # Create rows of videos
            rows = []
            row = []
            video_items = list(videos_data.items())
            for i, (video_key, video_data) in enumerate(video_items):
                row.append((video_key, video_data))
                if (i + 1) % num_cols == 0 or i == num_videos - 1:
                    rows.append(row)
                    row = []
            
            # Display videos in a grid
            for row_idx, row in enumerate(rows):
                cols = st.columns(num_cols)
                for i, (video_key, video_data) in enumerate(row):
                    with cols[i]:
                        st.write(f"**{video_data['name']}** ({video_data['original_size']:.2f} MB)")
                        
                        # Show video thumbnail
                        st.video(video_data["path"])

                        # Checkbox to select for compression
                        videos_data[video_key]["selected_for_compression"] = st.checkbox(
                            "Select for compression",
                            value=True,
                            key=f"select_{video_key}"
                        )
                        
                        # Estimate compressed size
                        if video_data["video_info"]:
                            estimated_size = estimate_size(
                                video_data["video_info"],
                                resolution=resolution,
                                remove_audio=remove_audio,
                                fps=fps,
                                bitrate=bitrate
                            )
                            
                            if estimated_size:
                                # Show original and estimated sizes
                                st.metric(
                                    "Estimated Size", 
                                    f"{estimated_size:.2f} MB"
                                )
                                st.metric(
                                    "Estimated Reduction",
                                    f"{(1 - estimated_size/video_data['original_size']) * 100:.1f}%"
                                )
        # Create layout for videos and compression
        # Compress button - works on selected videos
        if st.button("🎬 Compress Videos", use_container_width=True, type="primary"):
            # Check if any videos are selected
            selected_videos = [v for k, v in videos_data.items() if v["selected_for_compression"]]
            
            if not selected_videos:
                st.warning("Please select at least one video to compress.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Process each selected video
                compressed_videos = []
                
                for i, video_data in enumerate(selected_videos):
                    status_text.text(f"Compressing {video_data['name']}...")
                    
                    # Create output path
                    output_filename = f"compressed_{video_data['name']}"
                    output_path = os.path.join(tempfile.gettempdir(), output_filename)
                    
                    # Compress the video
                    success = compress_video(
                        video_data["path"], 
                        output_path,
                        resolution=resolution,
                        remove_audio=remove_audio,
                        fps=fps,
                        bitrate=bitrate
                    )
                    
                    if success:
                        compressed_size = get_file_size(output_path)
                        compressed_videos.append({
                            "name": video_data["name"],
                            "output_path": output_path,
                            "original_size": video_data["original_size"],
                            "compressed_size": compressed_size
                        })
                    
                    # Update progress
                    progress_bar.progress((i + 1) / len(selected_videos))
                
                # Clear the progress indicators
                status_text.empty()
                progress_bar.empty()
                
                # Display the results
                if compressed_videos:
                    st.subheader("Compression Results")
                    
                    # Total statistics
                    total_original = sum(v["original_size"] for v in compressed_videos)
                    total_compressed = sum(v["compressed_size"] for v in compressed_videos)
                    
                    stat_cols = st.columns(3)
                    stat_cols[0].metric(
                        "Total Original Size", 
                        f"{total_original:.2f} MB"
                    )
                    stat_cols[1].metric(
                        "Total Compressed Size", 
                        f"{total_compressed:.2f} MB"
                    )
                    stat_cols[2].metric(
                        "Total Reduction", 
                        f"{(1 - total_compressed/total_original) * 100:.1f}%"
                    )
                    
                    # Display compressed videos in a grid layout based on count
                    st.write("### Compressed Videos")
                    
                    # Determine number of columns (2, 3, or 4 based on the number of videos)
                    num_videos = len(compressed_videos)
                    num_cols = min(max(2, num_videos), 4)  # At least 2, at most 4 columns
                    
                    # Create rows of videos
                    rows = []
                    row = []
                    for i, video in enumerate(compressed_videos):
                        row.append(video)
                        if (i + 1) % num_cols == 0 or i == num_videos - 1:
                            rows.append(row)
                            row = []
                    
                    # Display videos in a grid
                    for row_idx, row in enumerate(rows):
                        cols = st.columns(num_cols)
                        for i, video in enumerate(row):
                            with cols[i]:
                                vid_key = f"compressed_{row_idx}_{i}"
                                # Title and metrics
                                st.write(f"**{video['name']}**")
                                st.metric(
                                    "Size Reduction", 
                                    f"{(1 - video['compressed_size']/video['original_size']) * 100:.1f}%"
                                )
                                
                                # Show the compressed video
                                with open(video["output_path"], "rb") as file:
                                    st.video(file.read())
                                
                                # Provide download link
                                with open(video["output_path"], "rb") as file:
                                    st.download_button(
                                        label=f"Download",
                                        data=file,
                                        file_name=f"compressed_{video['name']}",
                                        mime="video/mp4",
                                        use_container_width=True
                                    )

        # Clean up temp files when app is closed or rerun
        for video_data in videos_data.values():
            try:
                os.remove(video_data["path"])
            except:
                pass

if __name__ == "__main__":
    main()
