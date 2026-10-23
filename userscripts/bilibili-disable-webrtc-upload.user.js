// ==UserScript==
// @name         常见视频直播平台 WebRTC 上传防护
// @namespace    local.video.webrtc-upload-guard
// @version      1.1.0
// @description  阻止 WebRTC 数据通道业务数据和音视频轨道发送，保留建连及接收；不阻止协议控制流量或 HTTP 上传。
// @match        *://*.bilibili.com/*
// @match        *://*.douyu.com/*
// @match        *://*.huya.com/*
// @match        *://v.qq.com/*
// @match        *://*.video.qq.com/*
// @match        *://*.iqiyi.com/*
// @match        *://*.youku.com/*
// @match        *://*.tudou.com/*
// @match        *://*.mgtv.com/*
// @match        *://*.miguvideo.com/*
// @match        *://*.migu.cn/*
// @match        *://*.acfun.cn/*
// @match        *://*.douyin.com/*
// @match        *://*.ixigua.com/*
// @match        *://*.toutiao.com/*
// @match        *://tv.sohu.com/*
// @match        *://film.sohu.com/*
// @match        *://*.pptv.com/*
// @match        *://*.yangshipin.cn/*
// @match        *://*.cctv.com/*
// @run-at       document-start
// @grant        none
// @sandbox      raw
// ==/UserScript==

(() => {
  'use strict';
  const prefix = '[WebRTC 上传防护]';
  const warned = new Set();
  function warnOnce(name) {
    if (warned.has(name)) return;
    warned.add(name);
    console.warn(prefix, name, '已阻止；需要双向数据通信的直播可能无法正常播放。');
  }
  function denied(name) {
    warnOnce(name);
    return new DOMException('WebRTC outgoing application data/media blocked by userscript.', 'NotAllowedError');
  }
  function patch(proto, name, replacement) {
    if (!proto || typeof proto[name] !== 'function') return;
    try {
      const descriptor = Object.getOwnPropertyDescriptor(proto, name);
      Object.defineProperty(proto, name, { ...descriptor, value: replacement });
    } catch (error) {
      console.error(prefix, '无法安装拦截：', name, error);
    }
  }

  // Covers locally created AND remotely opened channels. Keep channel creation,
  // native connection state and incoming message events intact.
  patch(window.RTCDataChannel?.prototype, 'send', function () {
    throw denied('RTCDataChannel.send');
  });

  const peer = window.RTCPeerConnection?.prototype;
  patch(peer, 'addTrack', function () {
    throw denied('RTCPeerConnection.addTrack');
  });
  patch(peer, 'addStream', function () {
    throw denied('RTCPeerConnection.addStream');
  });

  const addTransceiver = peer?.addTransceiver;
  patch(peer, 'addTransceiver', function (trackOrKind, init = {}) {
    const kind = typeof trackOrKind === 'string' ? trackOrKind : trackOrKind?.kind;
    if (!['audio', 'video'].includes(kind)) {
      return addTransceiver.call(this, trackOrKind, init);
    }
    // Passing a kind instead of a track leaves the sender without media.
    // Retain explicit inactive transceivers rather than changing negotiation.
    const direction = init.direction === 'inactive' ? 'inactive' : 'recvonly';
    return addTransceiver.call(this, kind, { ...init, direction });
  });

  const replaceTrack = window.RTCRtpSender?.prototype.replaceTrack;
  patch(window.RTCRtpSender?.prototype, 'replaceTrack', function (track) {
    if (track !== null) return Promise.reject(denied('RTCRtpSender.replaceTrack'));
    return replaceTrack.call(this, null);
  });

  // getUserMedia is deliberately left intact: camera/microphone permissions
  // do not control P2P data channels. Media transmission is blocked above.
  console.info(prefix, '已安装。阻止业务数据/媒体发送，允许接收及必要的 WebRTC 控制流量。');
})();
