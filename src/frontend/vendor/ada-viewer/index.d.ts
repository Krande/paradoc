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
    /**
     * Show adapy's native viewer controls (top navbar, selection tree,
     * object/group info panels). The vendor bundle currently shipped
     * with paradoc renders only the canvas + OrbitControls and ignores
     * this flag; it becomes live once a richer vendor build is dropped
     * in. Plumbing the option here so consumers don't have to re-call
     * mountViewer differently when that lands.
     */
    showControls?: boolean;
    onReady?: () => void;
    onError?: (err: Error) => void;
}
export interface MountedViewer {
    dispose: () => void;
}
export declare function mountViewer(element: HTMLElement, opts: MountViewerOptions): MountedViewer;
