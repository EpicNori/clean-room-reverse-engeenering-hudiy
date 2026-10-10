// Our own practical curves; not a claim about proprietary Hudiy preset values.
export const audioPresets = Object.freeze({
  Flat: Object.freeze(Array(15).fill(0)),
  Pop: Object.freeze([-1,-1,0,0,1,2,2,1,0,-1,-1,0,1,2,2]),
  Rock: Object.freeze([4,4,3,2,0,-1,-2,-1,0,1,2,3,4,4,3]),
  Jazz: Object.freeze([2,2,1,0,-1,-1,0,1,2,2,1,1,2,2,1]),
  Classical: Object.freeze([2,2,1,0,0,-1,-1,0,0,1,2,2,2,1,1]),
  'Bass boost': Object.freeze([6,6,5,4,3,2,1,0,0,0,0,0,0,0,0]),
  Voice: Object.freeze([-4,-4,-3,-2,-1,0,1,2,3,3,2,1,0,-1,-2]),
});
