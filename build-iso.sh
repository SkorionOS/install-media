#!/bin/bash

set -xe

if [ $EUID -ne 0 ]; then
	echo "$(basename $0) must be run as root"
	exit 1
fi

# get the directory of this script
work_dir="$(realpath $0|rev|cut -d '/' -f2-|rev)"

# configuration variables for the iso
output_dir="${work_dir}/output"
script_dir="${work_dir}/chimeraos"
temp_dir="${work_dir}/temp"

# create output directory if it doesn't exist yet
rm -rf "${output_dir}"
mkdir -p "${output_dir}"

rm -rf "${temp_dir}"
mkdir -p "${temp_dir}"

# add AUR packages to the build
AUR_PACKAGES="\
    aic8800d80-dkms \
    fpaste \
    frzr-sk \
    inputplumber-bin \
    pikaur \
    rtl88x2bu-dkms-git \
    rtw89-dkms-git \
    r8152-dkms \
    rtl8812au-dkms-git \
    rtl8814au-dkms-git \
    rtl8821au-dkms-git \
    rz608-fix-git \
"

ADDITIONAL_PACKAGES="\
    https://github.com/3003n/linux-chimeraos/releases/download/v6.15.4-5/linux-skchos-6.15.4-5-x86_64.pkg.tar.zst \
	https://github.com/3003n/linux-chimeraos/releases/download/v6.15.4-5/linux-skchos-headers-6.15.4-5-x86_64.pkg.tar.zst \
"

# create repo directory if it doesn't exist yet
LOCAL_REPO="${script_dir}/extra_pkg"
mkdir -p ${LOCAL_REPO}

# Clear temp repo directory (pikaur will create it with correct permissions)
rm -rf /tmp/temp_repo

# Build packages one by one with retry
BUILT_PACKAGES=()
total_packages=$(echo ${AUR_PACKAGES} | wc -w)
current=0

for package in ${AUR_PACKAGES}; do
    current=$((current + 1))
    echo "[$current/$total_packages] Building package: $package"
    
    # Retry up to 3 times
    success=false
    for retry in {1..3}; do
        if [ $retry -gt 1 ]; then
            echo "Retry attempt $((retry-1)) for: $package"
        fi
        
        PIKAUR_CMD="PKGDEST=/tmp/temp_repo pikaur --noconfirm -Sw ${package}"
        PIKAUR_RUN=(bash -c "${PIKAUR_CMD}")
        if [ -n "${BUILD_USER}" ]; then
            PIKAUR_RUN=(su "${BUILD_USER}" -c "${PIKAUR_CMD}")
        fi
        
        pushd /home/${BUILD_USER}
        if "${PIKAUR_RUN[@]}"; then
            BUILT_PACKAGES+=("$package")
            success=true
            echo "✅ Package $package built successfully"
            break
        else
            echo "Build failed (attempt $retry/3) for: $package"
        fi
        popd
    done
    
    # Exit on failure
    if [ "$success" = false ]; then
        echo "❌ Error: Package $package failed after 3 attempts"
        echo "Build aborted"
        exit 1
    fi
done

echo "✅ All AUR packages built successfully (${#BUILT_PACKAGES[@]}/$total_packages)"

# copy all built packages to the repo
cp /tmp/temp_repo/* ${LOCAL_REPO}

# download additional packages to the repo
curl -L --remote-name-all --output-dir ${LOCAL_REPO} ${ADDITIONAL_PACKAGES}

# Add the repo to the build
repo-add ${LOCAL_REPO}/chimeraos.db.tar.gz ${LOCAL_REPO}/*.pkg.*
sed "s|LOCAL_REPO|$LOCAL_REPO|g" $script_dir/pacman.conf.template > $script_dir/pacman.conf

# make the container build the iso
mkarchiso -v -w "${temp_dir}" -o "${output_dir}" "${script_dir}"

# allow git command to work
git config --global --add safe.directory "${work_dir}"

ISO_FILE_PATH=$(ls ${output_dir}/*.iso)
ISO_FILE_NAME=$(basename "${ISO_FILE_PATH}")
VERSION=$(echo "${ISO_FILE_NAME}" | cut -c14-23 | sed 's/\./-/g')
ID=$(git rev-parse --short HEAD)

# Generate checksum file with appropriate name based on variant
SHA256_FILE_NAME="sha256sum"
if [ "${VARIANT_SUFFIX}" = "-lite" ]; then
	SHA256_FILE_NAME="sha256sum-lite"
fi
SHA256_FILE_NAME="${SHA256_FILE_NAME}.txt"

pushd ${output_dir}
sha256sum ${ISO_FILE_NAME} > ${SHA256_FILE_NAME}
cat ${SHA256_FILE_NAME}
popd

if [ -f "${GITHUB_OUTPUT}" ]; then
	echo "iso_file_name=${ISO_FILE_NAME}" >> "${GITHUB_OUTPUT}"
	echo "version=${VERSION}" >> "${GITHUB_OUTPUT}"
	echo "id=${ID}" >> "${GITHUB_OUTPUT}"
else
	echo "No github output file set"
fi
