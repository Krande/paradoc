export interface CameraPreset {
    name: string;
    azimuth_deg: number;
    elevation_deg: number;
    roll_deg?: number;
    target?: 'bbox_center';
    distance?: 'fit' | number;
    fov_deg?: number;
    margin?: number;
}
export interface MountViewerOptions {
    modelBytes: Uint8Array;
    camera: CameraPreset;
    caption?: string;
    onReady?: () => void;
    onError?: (err: Error) => void;
}
export interface MountedViewer {
    dispose: () => void;
}
export declare function mountViewer(element: HTMLElement, opts: MountViewerOptions): MountedViewer;
