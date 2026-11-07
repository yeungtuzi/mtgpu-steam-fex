cmake_minimum_required(VERSION 3.16)
project(ReunionLiteQt CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(Qt6 REQUIRED COMPONENTS Widgets)
add_executable(reunion-lite-qt
    src/core/ini.cpp
    src/core/campaign.cpp
    src/core/fs_generic.cpp
    src/core/launch.cpp
    src/platform/linux/encoding.cpp
    src/app_qt.cpp)
target_include_directories(reunion-lite-qt PRIVATE src src/core src/platform/linux)
target_link_libraries(reunion-lite-qt PRIVATE Qt6::Widgets)
