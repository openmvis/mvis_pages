// Makers and partners who shared device recordings or units. Used by the Acknowledgements cards (PartnerCards)
// and the homepage device band (HomeDevices). Logos come from each company's own website; a company without one
// gets its name on the plate.
import looper from '../assets/partners/looperrobotics.webp';
import gilabs from '../assets/partners/gilabs.svg';
import alg from '../assets/partners/alg.png';
import tujian from '../assets/partners/tujian.png';
import dibuli from '../assets/partners/dibuli.svg';
import feekassFront from '../assets/partners/feekass-card-front.webp';
import feekassBack from '../assets/partners/feekass-card-back.webp';

export type Link = { label: string; href: string };
export type Partner = {
  name: string;
  full?: string;
  site: string;
  logo?: { src: string };
  shared: string;
  devices: Link[];
  people?: string[];
  contact?: Link[];
  // Name card the contact sent for this page: both sides, plus the same details as text (images are not readable
  // by screen readers or search). Rendered as a closed fold on the Acknowledgements card.
  card?: { front: { src: string }; back: { src: string }; lines: { label: string; text: string; href?: string }[] };
};

export const partners: Partner[] = [
  {
    name: 'LooperRobotics', site: 'https://looper-robotics.com/', logo: looper,
    shared: 'Hand-held and robot-arm recordings',
    devices: [{ label: 'Insight 9', href: '/devices/looper-insight9/' }, { label: 'Looper example', href: '/benchmark/examples/looper-insight9/' }],
    people: ['<a href="https://www.linkedin.com/in/qinrui-yan-3625aa90">Qinrui Yan</a> and <a href="https://www.linkedin.com/in/junjie-tang-271b8033a">Junjie Tang</a>, who collected the recordings and supported sharing this work openly'],
  },
  {
    name: 'General Intelligence Labs', site: 'https://www.gilabs.xyz/', logo: gilabs,
    shared: 'Head-worn camera recordings, and gilabs-examples on the Hub',
    devices: [{ label: 'GI Ego1', href: '/devices/gi-ego1/' }, { label: 'GI EGO1GS', href: '/devices/gi-ego1gs/' }],
    people: ['Xie Junyuan (解浚源)'],
  },
  {
    name: 'ALG Tech', full: 'Shenzhen Aili-Light Technology', site: 'https://www.aili-light.com/', logo: alg,
    shared: 'GMSL2 stereo module recordings',
    devices: [{ label: 'AVS111C-Y', href: '/devices/alg-avs111c/' }, { label: 'AVS115D-Y', href: '/devices/alg-avs115d/' }],
    people: ['Xie Jiebin (谢捷斌), business development'],
    contact: [{ label: 'jimmy@aili-light.com', href: 'mailto:jimmy@aili-light.com' }],
  },
  {
    name: 'Tujian', full: 'Shenzhen Tujian Intelligent Technology', site: 'https://tujian.tech', logo: tujian,
    shared: 'Four-camera inertial module recording',
    devices: [{ label: 'CyperStereo', href: '/devices/cyperstereo/' }],
  },
  {
    name: 'DIBULI', full: '迪博凌（上海）科技有限公司, Shanghai', site: 'https://dibuli.com', logo: dibuli,
    shared: 'The camera + IMU calibration recordings they publish',
    devices: [{ label: 'Prism-A4L', href: '/devices/dibuli-prism-a4l/' }],
    people: ['Li Xiangfu (李相辅)'],
  },
  {
    name: 'Hampo', full: 'Dongguan Hampo Electronic Technology', site: 'https://www.hampotech.com/',
    shared: 'Stereo fisheye module recording',
    devices: [{ label: 'Hampo stereo module', href: '/devices/hampo/' }],
    people: ['Zhou Yuhua (周宇华), sales manager'],
    contact: [{ label: 'cannychow@dghpdz.cn', href: 'mailto:cannychow@dghpdz.cn' }],
  },
  {
    name: 'RoboBaton', site: 'https://hessian-matrix.github.io/RoboBaton_Neo_docs/',
    shared: 'Calibration recording of their Neo VIO module, hosted on the Hub (community/robobaton-neo)',
    devices: [{ label: 'Neo', href: '/devices/robobaton-neo/' }],
    // people: pending the contact's OK to be named (2026-11-19)
  },
  {
    name: 'Feekass', full: 'Shenzhen Feekass (Feikasi Industrial), brand Borme',
    site: 'https://www.alibaba.com/product-detail/1080P-Global-Shutter-Binocular-IMU-Camera_1601882874490.html',
    shared: 'Recordings of two headset units',
    devices: [{ label: 'XQ20 headset', href: '/devices/xq20/' }],
    people: ['Peyton Zhao (Zhao Peiyu, 赵培禹), sales representative'],
    contact: [{ label: 'borme02@fkscam.com', href: 'mailto:borme02@fkscam.com' }],
    card: {
      front: feekassFront, back: feekassBack,
      lines: [
        { label: 'WhatsApp / mobile', text: '+86 130 5808 0347', href: 'https://wa.me/8613058080347' },
        { label: 'WeChat', text: 'zpyyy0111' },
        { label: 'Email', text: 'borme02@fkscam.com', href: 'mailto:borme02@fkscam.com' },
        { label: 'Store', text: 'XQ20 on Alibaba', href: 'https://www.alibaba.com/product-detail/1080P-Global-Shutter-Binocular-IMU-Camera_1601882874490.html' },
      ],
    },
  },
];
