# An example of using Dear ImGui with Glfw in python
# Here, the backend rendering is implemented in C++: see calls to C++ native functions:
#   imgui.backends.glfw_xxxx()
#

# imgui_bundle can be used to run imgui with an almost line by line translation from C++ to python
#
# This file a direct adaptation of an imgui example (imgui/examples/example_glfw_opengl3/main.cpp)
# (see https://github.com/ocornut/imgui/blob/master/examples/example_glfw_opengl3/main.cpp)


import os.path
import sys
import platform
import OpenGL.GL as GL  # type: ignore
from imgui_bundle import imgui

# Always import glfw *after* imgui_bundle
# (since imgui_bundle will set the correct path where to look for the correct version of the glfw dynamic library)
import glfw  # type: ignore

##########################################
import ctypes
import numpy as np
import util
import imageio
import util_gau
import tkinter as tk
from tkinter import filedialog
import os
import sys
import argparse
from renderer_ogl import OpenGLRenderer, GaussianRenderBase

# Add the directory containing main.py to the Python path
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(dir_path)

# Change the current working directory to the script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))


g_camera = util.Camera(720, 1280)
BACKEND_OGL=0
BACKEND_CUDA=1
g_renderer_list = [
    None, # ogl
]
g_renderer_idx = BACKEND_OGL
g_renderer: GaussianRenderBase = g_renderer_list[g_renderer_idx]
g_scale_modifier = 1.
g_auto_sort = False
g_show_control_win = True
g_show_help_win = True
g_show_camera_win = False
g_render_mode_tables = ["Gaussian Ball", "Flat Ball", "Billboard", "Depth", "SH:0", "SH:0~1", "SH:0~2", "SH:0~3 (default)"]
g_render_mode = 7

##########################################

def glfw_error_callback(error: int, description: str) -> None:
    sys.stderr.write(f"Glfw Error {error}: {description}\n")

##########################################
def cursor_pos_callback(window, xpos, ypos):
    if imgui.get_io().want_capture_mouse:
        g_camera.is_leftmouse_pressed = False
        g_camera.is_rightmouse_pressed = False
    g_camera.process_mouse(xpos, ypos)

def mouse_button_callback(window, button, action, mod):
    if imgui.get_io().want_capture_mouse:
        return
    pressed = action == glfw.PRESS
    g_camera.is_leftmouse_pressed = (button == glfw.MOUSE_BUTTON_LEFT and pressed)
    g_camera.is_rightmouse_pressed = (button == glfw.MOUSE_BUTTON_RIGHT and pressed)

def wheel_callback(window, dx, dy):
    g_camera.process_wheel(dx, dy)

def key_callback(window, key, scancode, action, mods):
    if action == glfw.REPEAT or action == glfw.PRESS:
        if key == glfw.KEY_Q:
            g_camera.process_roll_key(1)
        elif key == glfw.KEY_E:
            g_camera.process_roll_key(-1)

def update_camera_pose_lazy():
    if g_camera.is_pose_dirty:
        g_renderer.update_camera_pose(g_camera)
        g_camera.is_pose_dirty = False

def update_camera_intrin_lazy():
    if g_camera.is_intrin_dirty:
        g_renderer.update_camera_intrin(g_camera)
        g_camera.is_intrin_dirty = False

def update_activated_renderer_state(gaus: util_gau.GaussianData):
    g_renderer.update_gaussian_data(gaus)
    g_renderer.sort_and_update(g_camera)
    g_renderer.set_scale_modifier(g_scale_modifier)
    g_renderer.set_render_mod(g_render_mode - 3)
    g_renderer.update_camera_pose(g_camera)
    g_renderer.update_camera_intrin(g_camera)
    g_renderer.set_render_reso(g_camera.w, g_camera.h)

def window_resize_callback(window, width, height):
    GL.glViewport(0, 0, width, height)
    g_camera.update_resolution(height, width)
    g_renderer.set_render_reso(width, height)
##########################################

def main() -> None:
##########################################
    global g_camera, g_renderer, g_renderer_list, g_renderer_idx, g_scale_modifier, g_auto_sort, \
    g_show_control_win, g_show_help_win, g_show_camera_win, \
    g_render_mode, g_render_mode_tables
##########################################

    # Setup window
    glfw.set_error_callback(glfw_error_callback)
    if not glfw.init():
        sys.exit(1)

    # Decide GL+GLSL versions
    # #if defined(IMGUI_IMPL_OPENGL_ES2)
    # // GL ES 2.0 + GLSL 100
    # const char* glsl_version = "#version 100";
    # glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 2);
    # glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 0);
    # glfwWindowHint(GLFW_CLIENT_API, GLFW_OPENGL_ES_API);
    if platform.system() == "Darwin":
        glsl_version = "#version 150"
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 2)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)  # // 3.2+ only
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL.GL_TRUE)
    else:
        # GL 3.0 + GLSL 130
        glsl_version = "#version 130"
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 0)
        # glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE) # // 3.2+ only
        # glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)

    # Create window with graphics context
    window = glfw.create_window(
        g_camera.w, g_camera.h, "Dear ImGui GLFW+OpenGL3 example", None, None
    )
    if window is None:
        sys.exit(1)
    glfw.make_context_current(window)
    glfw.swap_interval(1)  # // Enable vsync

##########################################
    root = tk.Tk()  # used for file dialog
    root.withdraw()
    
    glfw.set_cursor_pos_callback(window, cursor_pos_callback)
    glfw.set_mouse_button_callback(window, mouse_button_callback)
    glfw.set_scroll_callback(window, wheel_callback)
    glfw.set_key_callback(window, key_callback)
    
    glfw.set_window_size_callback(window, window_resize_callback)


    # init renderer
    g_renderer_list[BACKEND_OGL] = OpenGLRenderer(g_camera.w, g_camera.h)
    try:
        from renderer_cuda import CUDARenderer
        g_renderer_list += [CUDARenderer(g_camera.w, g_camera.h)]
    except ImportError:
        g_renderer_idx = BACKEND_OGL
    else:
        g_renderer_idx = BACKEND_CUDA

    g_renderer = g_renderer_list[g_renderer_idx]

    # gaussian data
    gaussians = util_gau.naive_gaussian()
    update_activated_renderer_state(gaussians)

    # screen plane
    plane_buffer = [-1.0, -1.0, 0.0, 0.0, 0.0,
                1.0, -1.0, 0.0, 1.0, 0.0,
                1.0, 1.0, 0.0, 1.0, 1.0,
                -1.0, 1.0, 0.0, 0.0, 1.0]

    plane_buffer = np.array(plane_buffer, dtype=np.float32)

    plane_indices = [0, 1, 2, 2, 3, 0]
    plane_indices = np.array(plane_indices, dtype=np.uint32)
    plane_program = util.load_shaders('shaders/framebuffer_vert.glsl', 'shaders/framebuffer_frag.glsl')
    # VAO and VBO
    VAO = GL.glGenVertexArrays(1)
    VBO = GL.glGenBuffers(1)
    EBO = GL.glGenBuffers(1)

    # Plane VAO
    GL.glBindVertexArray(VAO)
    # Plane Vertex Buffer Object
    GL.glBindBuffer(GL.GL_ARRAY_BUFFER, VBO)
    GL.glBufferData(GL.GL_ARRAY_BUFFER, plane_buffer.nbytes, plane_buffer, GL.GL_STATIC_DRAW)

    GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, EBO)
    GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, plane_indices.nbytes, plane_indices, GL.GL_STATIC_DRAW)

    # plane vertices
    GL.glEnableVertexAttribArray(0)
    GL.glVertexAttribPointer(0, 3, GL.GL_FLOAT, GL.GL_FALSE, plane_buffer.itemsize * 5, ctypes.c_void_p(0))
    # plane textures
    GL.glEnableVertexAttribArray(1)
    GL.glVertexAttribPointer(1, 2, GL.GL_FLOAT, GL.GL_FALSE, plane_buffer.itemsize * 5, ctypes.c_void_p(12))

    texture = GL.glGenTextures(1)

    # create texture for the plane
    GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
    # texture wrapping params
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_REPEAT)
    # texture filtering params
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
    # GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, g_camera.w, g_camera.h, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
    GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGB, g_camera.w, g_camera.h, 0, GL.GL_RGB, GL.GL_UNSIGNED_BYTE, None)
    GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

    depth_buff = GL.glGenRenderbuffers(1)
    GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, depth_buff)
    GL.glRenderbufferStorage(GL.GL_RENDERBUFFER, GL.GL_DEPTH_COMPONENT, g_camera.w, g_camera.h)

    FBO = GL.glGenFramebuffers(1)
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, FBO)
    GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, texture, 0)
    GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER, GL.GL_DEPTH_ATTACHMENT, GL.GL_RENDERBUFFER, depth_buff)
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
##########################################

    # Setup Dear ImGui context
    # IMGUI_CHECKVERSION();
    imgui.create_context()
    io = imgui.get_io()
    io.config_flags |= (
        imgui.ConfigFlags_.nav_enable_keyboard
    )  # Enable Keyboard Controls
    # io.config_flags |= imgui.ConfigFlags_.nav_enable_gamepad # Enable Gamepad Controls
    io.config_flags |= imgui.ConfigFlags_.docking_enable  # Enable docking
    # io.config_flags |= imgui.ConfigFlags_.viewports_enable # Enable Multi-Viewport / Platform Windows
    # io.config_viewports_no_auto_merge = True
    # io.config_viewports_no_task_bar_icon = True

    # Setup Dear ImGui style
    imgui.style_colors_dark()
    # imgui.style_colors_classic()

    # When viewports are enabled we tweak WindowRounding/WindowBg so platform windows can look identical to regular ones.
    style = imgui.get_style()
    if io.config_flags & imgui.ConfigFlags_.viewports_enable:
        style.window_rounding = 0.0
        window_bg_color = style.color_(imgui.Col_.window_bg)
        window_bg_color.w = 1.0
        style.set_color_(imgui.Col_.window_bg, window_bg_color)

    # Setup Platform/Renderer backends
    # import ctypes

    # You need to transfer the window address to imgui.backends.glfw_init_for_opengl
    # proceed as shown below to get it.
    window_address = ctypes.cast(window, ctypes.c_void_p).value
    imgui.backends.glfw_init_for_opengl(window_address, True)

    imgui.backends.opengl3_init(glsl_version)

    # # // Load Fonts
    # # // - If no fonts are loaded, dear imgui will use the default font. You can also load multiple fonts and use imgui.PushFont()/PopFont() to select them.
    # # // - AddFontFromFileTTF() will return the ImFont* so you can store it if you need to select the font among multiple.
    # # // - If the file cannot be loaded, the function will return NULL. Please handle those errors in your application (e.g. use an assertion, or display an error and quit).
    # # // - The fonts will be rasterized at a given size (w/ oversampling) and stored into a texture when calling ImFontAtlas::Build()/GetTexDataAsXXXX(), which ImGui_ImplXXXX_NewFrame below will call.
    # # // - Read 'docs/FONTS.md' for more instructions and details.
    # #     // - Remember that in C/C++ if you want to include a backslash \ in a string literal you need to write a double backslash \\ !
    # # //io.Fonts->AddFontDefault();
    # # //io.Fonts->AddFontFromFileTTF("../../misc/fonts/Roboto-Medium.ttf", 16.0f);
    # # //io.Fonts->AddFontFromFileTTF("../../misc/fonts/Cousine-Regular.ttf", 15.0f);
    # # //io.Fonts->AddFontFromFileTTF("../../misc/fonts/DroidSans.ttf", 16.0f);
    # # //io.Fonts->AddFontFromFileTTF("../../misc/fonts/ProggyTiny.ttf", 10.0f);
    # # //ImFont* font = io.Fonts->AddFontFromFileTTF("c:\\Windows\\Fonts\\ArialUni.ttf", 18.0f, NULL, io.Fonts->GetGlyphRangesJapanese());
    # # //IM_ASSERT(font != NULL);

    # # Load font example, with a merged font for icons
    # # ------------------------------------------------
    # # i. Load default font
    # font_atlas = imgui.get_io().fonts
    # font_atlas.add_font_default()
    # this_dir = os.path.dirname(__file__)
    # font_size_pixel = 48.0
    # # i. Load another font...
    # font_filename = "Akronim-Regular.ttf"
    # font_atlas = imgui.get_io().fonts
    # glyph_range = font_atlas.get_glyph_ranges_default()
    # custom_font = font_atlas.add_font_from_file_ttf(
    #     filename=font_filename,
    #     size_pixels=font_size_pixel,
    #     glyph_ranges_as_int_list=glyph_range,
    # )
    # # ii. ... And merge icons into the previous font
    # from imgui_bundle import icons_fontawesome

    # font_filename = "assets/fontawesome-webfont.ttf"
    # font_config = imgui.ImFontConfig()
    # font_config.merge_mode = True
    # icons_range = [icons_fontawesome.ICON_MIN_FA, icons_fontawesome.ICON_MAX_FA, 0]
    # custom_font = font_atlas.add_font_from_file_ttf(
    #     filename=font_filename,
    #     size_pixels=font_size_pixel,
    #     glyph_ranges_as_int_list=icons_range,
    #     font_cfg=font_config,
    # )

    # Our state
    show_demo_window = False
    show_another_window = False
    clear_color = [0.45, 0.55, 0.60, 1.00]
    f = 0.0
    counter = 0

    # Main loop
    while not glfw.window_should_close(window):

        # // Poll and handle events (inputs, window resize, etc.)
        # // You can read the io.WantCaptureMouse, io.WantCaptureKeyboard flags to tell if dear imgui wants to use your inputs.
        # // - When io.WantCaptureMouse is true, do not dispatch mouse input data to your main application, or clear/overwrite your copy of the mouse data.
        # // - When io.WantCaptureKeyboard is true, do not dispatch keyboard input data to your main application, or clear/overwrite your copy of the keyboard data.
        # // Generally you may always pass all inputs to dear imgui, and hide them from your application based on those two flags.
        glfw.poll_events()

        # Start the Dear ImGui frame
        imgui.backends.opengl3_new_frame()
        imgui.backends.glfw_new_frame()
        imgui.new_frame()

        GL.glClearColor(0, 0, 0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        # 1. Show the big demo window (Most of the sample code is in imgui.ShowDemoWindow()! You can browse its code to learn more about Dear ImGui!).
        if show_demo_window:
            show_demo_window = imgui.show_demo_window(show_demo_window)

        # 2. Show a simple window that we create ourselves. We use a Begin/End pair to created a named window.
        def show_simple_window() -> None:
            nonlocal show_demo_window, show_another_window, clear_color, counter, f
            # static float f = 0.0f;
            # static int counter = 0;
            imgui.begin(
                "Hello, world!"
            )  # Create a window called "Hello, world!" and append into it.

            # # Demo custom font
            # _id = id(custom_font)
            # imgui.push_font(custom_font)
            # imgui.text("Hello " + icons_fontawesome.ICON_FA_SMILE)
            # imgui.pop_font()

            imgui.text(
                "This is some useful text."
            )  # Display some text (you can use a format strings too)
            _, show_demo_window = imgui.checkbox(
                "Demo Window", show_demo_window
            )  # Edit bools storing our window open/close state
            _, show_another_window = imgui.checkbox(
                "Another Window", show_another_window
            )

            _, f = imgui.slider_float(
                "float", f, 0.0, 1.0
            )  # Edit 1 float using a slider from 0.0f to 1.0f
            _, clear_color = imgui.color_edit4(
                "clear color", clear_color
            )  # Edit 4 floats representing a color

            if imgui.button(
                "Button"
            ):  # Buttons return true when clicked (most widgets return true when edited/activated)
                counter += 1

            imgui.same_line()
            imgui.text(f"counter = {counter}")

            imgui.text(
                f"Application average {1000.0 / imgui.get_io().framerate} ms/frame ({imgui.get_io().framerate:.1f} FPS)"
            )
            imgui.end()

        # show_simple_window()

        # 3. Show another simple window.
        def gui_another_window() -> None:
            nonlocal show_another_window
            if show_another_window:
                imgui.begin(
                    "Another Window", show_another_window
                )  # Pass a pointer to our bool variable (the window will have a closing button that will clear the bool when clicked)
                imgui.text("Hello from another window!")
                if imgui.button("Close Me"):
                    show_another_window = False
                imgui.end()

        gui_another_window()
        
        show_simple_window()

##########################################
        update_camera_pose_lazy()
        update_camera_intrin_lazy()

        # imgui ui
        if imgui.begin_main_menu_bar():
            if imgui.begin_menu("Window", True):
                clicked, g_show_control_win = imgui.menu_item(
                    "Show Control", None, g_show_control_win
                )
                clicked, g_show_help_win = imgui.menu_item(
                    "Show Help", None, g_show_help_win
                )
                clicked, g_show_camera_win = imgui.menu_item(
                    "Show Camera Control", None, g_show_camera_win
                )
                imgui.end_menu()
            imgui.end_main_menu_bar()
        
        if g_show_control_win:
            if imgui.begin("Control", True):
                # rendering backend
                changed, g_renderer_idx = imgui.combo("backend", g_renderer_idx, ["ogl", "cuda"][:len(g_renderer_list)])
                if changed:
                    g_renderer = g_renderer_list[g_renderer_idx]
                    update_activated_renderer_state(gaussians)

                imgui.text(f"fps = {imgui.get_io().framerate:.1f}")

                changed, g_renderer.reduce_updates = imgui.checkbox(
                        "reduce updates", g_renderer.reduce_updates,
                    )

                imgui.text(f"# of Gaus = {len(gaussians)}")
                if imgui.button(label='open ply'):
                    file_path = filedialog.askopenfilename(title="open ply",
                        initialdir="C:\\Users\\MSI_NB\\Downloads\\viewers",
                        filetypes=[('ply file', '.ply')]
                        )
                    if file_path:
                        try:
                            gaussians = util_gau.load_ply(file_path)
                            g_renderer.update_gaussian_data(gaussians)
                            g_renderer.sort_and_update(g_camera)
                        except RuntimeError as e:
                            pass
                
                # camera fov
                changed, g_camera.fovy = imgui.slider_float(
                    "fov", g_camera.fovy, 0.001, np.pi - 0.001, "fov = %.3f"
                )
                g_camera.is_intrin_dirty = changed
                update_camera_intrin_lazy()
                
                # scale modifier
                changed, g_scale_modifier = imgui.slider_float(
                    "_slider_label", g_scale_modifier, 0.1, 10, "scale modifier = %.3f"
                )
                imgui.same_line()
                if imgui.button(label="reset"):
                    g_scale_modifier = 1.
                    changed = True
                    
                if changed:
                    g_renderer.set_scale_modifier(g_scale_modifier)
                
                # render mode
                changed, g_render_mode = imgui.combo("shading", g_render_mode, g_render_mode_tables)
                if changed:
                    g_renderer.set_render_mod(g_render_mode - 4)
                
                # sort button
                if imgui.button(label='sort Gaussians'):
                    g_renderer.sort_and_update(g_camera)
                imgui.same_line()
                changed, g_auto_sort = imgui.checkbox(
                        "auto sort", g_auto_sort,
                    )
                if g_auto_sort:
                    g_renderer.sort_and_update(g_camera)
                
                if imgui.button(label='save image'):
                    width, height = glfw.get_framebuffer_size(window)
                    nrChannels = 3;
                    stride = nrChannels * width;
                    stride += (4 - stride % 4) if stride % 4 else 0
                    GL.glPixelStorei(GL.GL_PACK_ALIGNMENT, 4)
                    GL.glReadBuffer(GL.GL_FRONT)
                    bufferdata = GL.glReadPixels(0, 0, width, height, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
                    img = np.frombuffer(bufferdata, np.uint8, -1).reshape(height, width, 3)
                    imageio.imwrite("save.png", img[::-1])
                    # save intermediate information
                    # np.savez(
                    #     "save.npz",
                    #     gau_xyz=gaussians.xyz,
                    #     gau_s=gaussians.scale,
                    #     gau_rot=gaussians.rot,
                    #     gau_c=gaussians.sh,
                    #     gau_a=gaussians.opacity,
                    #     viewmat=g_camera.get_view_matrix(),
                    #     projmat=g_camera.get_project_matrix(),
                    #     hfovxyfocal=g_camera.get_htanfovxy_focal()
                    # )
                imgui.end()

        if g_show_camera_win:
            if imgui.button(label='rot 180'):
                g_camera.flip_ground()

            changed, g_camera.target_dist = imgui.slider_float(
                    "t", g_camera.target_dist, 1., 8., "target dist = %.3f"
                )
            if changed:
                g_camera.update_target_distance()

            changed, g_camera.rot_sensitivity = imgui.slider_float(
                    "r", g_camera.rot_sensitivity, 0.002, 0.1, "rotate speed = %.3f"
                )
            imgui.same_line()
            if imgui.button(label="reset r"):
                g_camera.rot_sensitivity = 0.02

            changed, g_camera.trans_sensitivity = imgui.slider_float(
                    "m", g_camera.trans_sensitivity, 0.001, 0.03, "move speed = %.3f"
                )
            imgui.same_line()
            if imgui.button(label="reset m"):
                g_camera.trans_sensitivity = 0.01

            changed, g_camera.zoom_sensitivity = imgui.slider_float(
                    "z", g_camera.zoom_sensitivity, 0.001, 0.05, "zoom speed = %.3f"
                )
            imgui.same_line()
            if imgui.button(label="reset z"):
                g_camera.zoom_sensitivity = 0.01

            changed, g_camera.roll_sensitivity = imgui.slider_float(
                    "ro", g_camera.roll_sensitivity, 0.003, 0.1, "roll speed = %.3f"
                )
            imgui.same_line()
            if imgui.button(label="reset ro"):
                g_camera.roll_sensitivity = 0.03

        if g_show_help_win:
            imgui.begin("Help", True)
            imgui.text("Open Gaussian Splatting PLY file \n  by click 'open ply' button")
            imgui.text("Use left click & move to rotate camera")
            imgui.text("Use right click & move to translate camera")
            imgui.text("Press Q/E to roll camera")
            imgui.text("Use scroll to zoom in/out")
            imgui.text("Use control panel to change setting")
            imgui.end()
        

        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, FBO)

        GL.glViewport(0,0,g_camera.w, g_camera.h)
        GL.glClearColor(0, 0, 0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        # GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ZERO)
        
        g_renderer.draw()

        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        # draw the plane
        GL.glUseProgram(plane_program)
        GL.glBindVertexArray(VAO)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glDrawElements(GL.GL_TRIANGLES, len(plane_indices), GL.GL_UNSIGNED_INT, None)

        # imgui.begin("Viewport", True)
        # imgui.image(texture, imgui.ImVec2(g_camera.w, g_camera.h),imgui.ImVec2(0,1), imgui.ImVec2(1,0))
        # imgui.end()


##########################################

        # Rendering
        imgui.render()
        display_w, display_h = glfw.get_framebuffer_size(window)
        GL.glViewport(0, 0, display_w, display_h)
        # GL.glClearColor(
        #     clear_color[0] * clear_color[3],
        #     clear_color[1] * clear_color[3],
        #     clear_color[2] * clear_color[3],
        #     clear_color[3],
        # )
        # GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        imgui.backends.opengl3_render_draw_data(imgui.get_draw_data())

        # Update and Render additional Platform Windows
        # (Platform functions may change the current OpenGL context, so we save/restore it to make it easier to paste this code elsewhere.
        #  For this specific demo app we could also call glfwMakeContextCurrent(window) directly)
        if io.config_flags & imgui.ConfigFlags_.viewports_enable > 0:
            backup_current_context = glfw.get_current_context()
            imgui.update_platform_windows()
            imgui.render_platform_windows_default()
            glfw.make_context_current(backup_current_context)

        glfw.swap_buffers(window)

    # Cleanup
    imgui.backends.opengl3_shutdown()
    imgui.backends.glfw_shutdown()
    imgui.destroy_context()

    glfw.destroy_window(window)
    glfw.terminate()


if __name__ == "__main__":
    main()
